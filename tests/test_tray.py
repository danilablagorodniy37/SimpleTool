"""Tray icon: appears, passes a click to the window via post and is removed cleanly (visible for a second)."""
import ctypes
import os
import sys
import threading
import time
import unittest
from ctypes import wintypes
from unittest import mock

ICON = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "app.ico")


class SID_AND_ATTRIBUTES(ctypes.Structure):
    _fields_ = [("Sid", wintypes.LPVOID), ("Attributes", wintypes.DWORD)]


def run_with_fewer_rights(function):
    """function() in a thread that acts as a copy of SimpleTool started with other rights: our own token with the
    user, Administrators and the logon session turned off (none of them grants access to objects we create with
    the default security) and a lower integrity level (High -> Medium, else Low). So the test needs neither a
    second user nor a UAC prompt."""
    k = ctypes.WinDLL("kernel32", use_last_error=True)
    a = ctypes.WinDLL("advapi32", use_last_error=True)
    k.GetCurrentProcess.restype = wintypes.HANDLE
    k.CloseHandle.argtypes = [wintypes.HANDLE]
    k.LocalFree.argtypes = [wintypes.LPVOID]
    a.OpenProcessToken.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)]
    a.GetTokenInformation.argtypes = [wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD,
                                      ctypes.POINTER(wintypes.DWORD)]
    a.CreateRestrictedToken.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD,
                                        ctypes.POINTER(SID_AND_ATTRIBUTES), wintypes.DWORD, wintypes.LPVOID,
                                        wintypes.DWORD, wintypes.LPVOID, ctypes.POINTER(wintypes.HANDLE)]
    a.DuplicateTokenEx.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPVOID, ctypes.c_int, ctypes.c_int,
                                   ctypes.POINTER(wintypes.HANDLE)]
    a.ConvertStringSidToSidW.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(wintypes.LPVOID)]
    a.SetTokenInformation.argtypes = [wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD]
    a.GetLengthSid.argtypes = [wintypes.LPVOID]
    a.SetThreadToken.argtypes = [wintypes.LPVOID, wintypes.HANDLE]

    def sid(text):
        value = wintypes.LPVOID()
        assert a.ConvertStringSidToSidW(text, ctypes.byref(value)), ctypes.get_last_error()
        return value

    token, restricted, impersonation = wintypes.HANDLE(), wintypes.HANDLE(), wintypes.HANDLE()
    assert a.OpenProcessToken(k.GetCurrentProcess(), 0x2 | 0x8, ctypes.byref(token))  # TOKEN_DUPLICATE | QUERY
    user, groups, size = ctypes.create_string_buffer(1024), ctypes.create_string_buffer(65536), wintypes.DWORD()
    assert a.GetTokenInformation(token, 1, user, len(user), ctypes.byref(size))  # TokenUser
    assert a.GetTokenInformation(token, 2, groups, len(groups), ctypes.byref(size))  # TokenGroups
    count = ctypes.cast(groups, ctypes.POINTER(wintypes.DWORD))[0]
    entries = ctypes.cast(ctypes.addressof(groups) + ctypes.sizeof(ctypes.c_void_p),
                          ctypes.POINTER(SID_AND_ATTRIBUTES * count)).contents
    admins = sid("S-1-5-32-544")
    disable = [SID_AND_ATTRIBUTES(SID_AND_ATTRIBUTES.from_buffer(user).Sid, 0), SID_AND_ATTRIBUTES(admins, 0)]
    disable += [SID_AND_ATTRIBUTES(e.Sid, 0) for e in entries
                if e.Attributes & 0xC0000000 == 0xC0000000]  # SE_GROUP_LOGON_ID
    disabled = (SID_AND_ATTRIBUTES * len(disable))(*disable)
    assert a.CreateRestrictedToken(token, 0, len(disable), disabled, 0, None, 0, None, ctypes.byref(restricted))
    # MAXIMUM_ALLOWED, SecurityImpersonation, TokenImpersonation
    assert a.DuplicateTokenEx(restricted, 0x02000000, None, 2, 2, ctypes.byref(impersonation))
    level = sid("S-1-16-8192" if ctypes.windll.shell32.IsUserAnAdmin() else "S-1-16-4096")
    label = SID_AND_ATTRIBUTES(level, 0x20)  # SE_GROUP_INTEGRITY
    assert a.SetTokenInformation(impersonation, 25, ctypes.byref(label),  # TokenIntegrityLevel
                                 ctypes.sizeof(label) + a.GetLengthSid(level))
    result = []

    def run():
        assert a.SetThreadToken(None, impersonation), ctypes.get_last_error()
        try:
            result.append(function())
        finally:
            a.RevertToSelf()

    thread = threading.Thread(target=run)
    thread.start()
    thread.join(10)
    for handle in (token, restricted, impersonation):
        k.CloseHandle(handle)
    for value in (admins, level):
        k.LocalFree(value)
    return result[0]


@unittest.skipUnless(sys.platform == "win32", "Windows tray")
class Tray(unittest.TestCase):
    def test_show_click_and_hide(self):
        import tray
        posted = []
        icon = tray.TrayIcon(ICON, "SimpleTool test", lambda: [(1, "Open", False), None, (2, "Exit", False)],
                             on_command=lambda command: None, on_open=lambda: None, post=posted.append)
        icon.show()
        try:
            self.assertTrue(icon.visible())
            hwnd = icon.hwnd
            icon.set_tooltip("SimpleTool test 2")
            send = ctypes.windll.user32.SendMessageW
            send.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
            send(hwnd, tray.WM_TRAY, 0, tray.WM_LBUTTONUP)  # click on the icon
            self.assertEqual(posted, [icon.on_open], "a click opens the window via post, not from the tray thread")

            class CHANGEFILTERSTRUCT(ctypes.Structure):
                _fields_ = [("cbSize", wintypes.DWORD), ("ExtStatus", wintypes.DWORD)]

            for message in (icon._taskbar_created, tray.WM_TRAY):  # Explorer can reach an elevated SimpleTool
                status = CHANGEFILTERSTRUCT(ctypes.sizeof(CHANGEFILTERSTRUCT))
                tray._user32.ChangeWindowMessageFilterEx(hwnd, message, tray.MSGFLT_ALLOW, ctypes.byref(status))
                self.assertEqual(status.ExtStatus, 1, "MSGFLTINFO_ALREADYALLOWED_FORWND")
        finally:
            icon.hide()
        self.assertFalse(icon.visible())
        self.assertFalse(icon._thread.is_alive())
        time.sleep(0.1)
        self.assertFalse(ctypes.windll.user32.IsWindow(hwnd), "the hidden tray window must be destroyed")


@unittest.skipUnless(sys.platform == "win32", "Windows events")
class SingleInstance(unittest.TestCase):
    def name(self):
        return f"Local\\simpletool-test-{os.getpid()}-{time.time_ns()}"

    def wait(self, woken):
        deadline = time.time() + 3
        while not woken and time.time() < deadline:
            time.sleep(0.02)

    def test_default_name_is_in_the_session_namespace(self):
        import tray
        self.assertEqual(tray.SingleInstance().name, "Local\\blagotech.SimpleTool.show")

    def test_second_copy_wakes_the_first(self):
        import tray
        name = self.name()
        first, second = tray.SingleInstance(name), tray.SingleInstance(name)
        woken, calls = [], []
        self.assertTrue(first.acquire())
        try:
            first.listen(lambda: woken.append(1))
            set_event = tray._kernel32.SetEvent
            with mock.patch.object(tray._user32, "AllowSetForegroundWindow", lambda pid: calls.append(pid) or 1), \
                    mock.patch.object(tray._kernel32, "SetEvent", lambda h: calls.append("signal") or set_event(h)):
                self.assertFalse(second.acquire(), "a second copy must not start")
            self.assertEqual(calls, [tray.ASFW_ANY, "signal"], "the first copy may bring its window to the front")
            self.wait(woken)
            self.assertEqual(woken, [1], "the first copy is asked to show its window")
        finally:
            first.release()
        self.assertTrue(second.acquire(), "after the first copy exits, a new one starts normally")
        second.release()

    def test_copy_with_fewer_rights_does_not_start(self):
        """SimpleTool runs as administrator and is started again without (or as another user): before, the second
        launch could not open the event and ran as a second copy. Elevated, the test checks it also wakes the first."""
        import tray
        name = self.name()
        first = tray.SingleInstance(name)
        woken = []
        self.assertTrue(first.acquire())
        try:
            first.listen(lambda: woken.append(1))
            self.assertFalse(run_with_fewer_rights(tray.SingleInstance(name).acquire), "a second copy must not start")
            if ctypes.windll.shell32.IsUserAnAdmin():  # a Medium launch may signal; a Low one cannot, but still exits
                self.wait(woken)
                self.assertEqual(woken, [1], "the elevated copy is asked to show its window")
        finally:
            first.release()


if __name__ == "__main__":
    unittest.main()
