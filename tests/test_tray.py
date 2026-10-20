"""Значок в трее: появляется, передаёт щелчок в окно через post и чисто удаляется (на секунду виден в трее)."""
import ctypes
import os
import sys
import time
import unittest
from ctypes import wintypes

ICON = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "app.ico")


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
            send(hwnd, tray.WM_TRAY, 0, tray.WM_LBUTTONUP)  # щелчок по значку
            self.assertEqual(posted, [icon.on_open], "a click opens the window via post, not from the tray thread")
        finally:
            icon.hide()
        self.assertFalse(icon.visible())
        self.assertFalse(icon._thread.is_alive())
        time.sleep(0.1)
        self.assertFalse(ctypes.windll.user32.IsWindow(hwnd), "the hidden tray window must be destroyed")


@unittest.skipUnless(sys.platform == "win32", "Windows events")
class SingleInstance(unittest.TestCase):
    def test_second_copy_wakes_the_first(self):
        import tray
        name = f"Local\simpletool-test-{os.getpid()}-{time.time_ns()}"
        first, second = tray.SingleInstance(name), tray.SingleInstance(name)
        woken = []
        self.assertTrue(first.acquire())
        try:
            first.listen(lambda: woken.append(1))
            self.assertFalse(second.acquire(), "a second copy must not start")
            deadline = time.time() + 3
            while not woken and time.time() < deadline:
                time.sleep(0.02)
            self.assertEqual(woken, [1], "the first copy is asked to show its window")
        finally:
            first.release()
        self.assertTrue(second.acquire(), "after the first copy exits, a new one starts normally")
        second.release()


if __name__ == "__main__":
    unittest.main()
