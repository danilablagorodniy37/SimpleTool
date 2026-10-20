"""The SimpleTool window: every page, details, language and theme opens without errors, the column is aligned.

The scan reads the real system (read-only). Apply, revert, snapshot restore, restore points and
any change to process memory are blocked by a tripwire during the test: the window cannot change anything.
"""
import shutil
import tempfile
import time
import tkinter as tk
import unittest
from unittest import mock

import engine
import i18n
import limiter
import main
import theme
import tweaks


def forbidden(*args, **kwargs):
    raise AssertionError("the UI test must never change the system")


class UiSmoke(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="simpletool-ui-test-")
        self.settings = {"lang": "en", "theme": "navy", "tray_hint_shown": True}  # no pop-up notifications
        self.patches = [
            mock.patch.object(engine, "data_dir", lambda: self.tmp),
            mock.patch.object(engine, "apply", forbidden),
            mock.patch.object(engine, "revert", forbidden),
            mock.patch.object(engine, "restore_snapshot", forbidden),
            mock.patch.object(engine, "create_restore_point", forbidden),
            mock.patch.object(main, "relaunch_as_admin", forbidden),
            mock.patch.object(limiter.WindowsApi, "trim", forbidden),
            mock.patch.object(limiter.WindowsApi, "set_hard_limit", forbidden),
            mock.patch.object(limiter.WindowsApi, "clear_hard_limit", forbidden),
            mock.patch.object(main, "load_settings", lambda: dict(self.settings)),
            mock.patch.object(main, "save_settings", lambda s: self.settings.update(s)),
        ]
        for patch in self.patches:
            patch.start()

    def tearDown(self):
        for patch in reversed(self.patches):
            patch.stop()
        theme.use("navy")
        theme.clear_cache()  # the images belong to a closed Tk window, the next test needs its own
        shutil.rmtree(self.tmp, ignore_errors=True)

    def pump(self, root, seconds):
        end = time.time() + seconds
        while time.time() < end:
            root.update()
            time.sleep(0.01)

    def open_app(self, admin):
        errors = []
        with mock.patch.object(engine, "is_admin", lambda: admin):
            root = tk.Tk()
            root.report_callback_exception = lambda kind, value, tb: errors.append(f"{kind.__name__}: {value}")
            root.geometry("1080x740+40+40")
            app = main.App(root)
        deadline = time.time() + 30
        while app.busy and time.time() < deadline:
            self.pump(root, 0.1)
        self.assertFalse(app.busy, "the scan did not finish")
        self.pump(root, 0.5)
        return root, app, errors

    def dialogs(self, root):
        return [w for w in root.winfo_children() if isinstance(w, tk.Toplevel)]

    def check_every_page(self, root, app):
        for page in main.PAGES:
            app.show_page(page)
            self.pump(root, 0.15)
            for key, widgets in list(app.cards.items()) + [(k, w) for k, w in app.service_cards.items()]:
                kind = "t" if key in app.cards else "s"
                app.toggle_details((kind, key), widgets)
            self.pump(root, 0.4)

    def test_admin_mode(self):
        root, app, errors = self.open_app(admin=True)
        try:
            self.assertEqual(self.dialogs(root), [], "no dialog expected when running as administrator")
            self.assertEqual(set(app.scan["checks"]), {t.id for t in tweaks.TWEAKS})
            self.check_every_page(root, app)
            # column: the right edges of the header buttons, the first card and the Apply button match
            app.show_page("privacy", animate=False)
            self.pump(root, 0.3)
            x0 = root.winfo_rootx()
            card = next(iter(app.cards.values()))["card"]
            edges = {app.controls.winfo_rootx() + app.controls.winfo_width() - x0,
                     card.winfo_rootx() + card.winfo_width() - x0,
                     app.apply_button.winfo_rootx() + app.apply_button.winfo_width() - x0}
            self.assertLessEqual(max(edges) - min(edges), 1, f"right edges differ: {edges}")
            # selecting a tweak enables the buttons, but nothing is pressed: the tripwire would block any apply
            app.toggle_select(tweaks.TWEAKS[0])
            self.assertTrue(app.apply_button.enabled)
            for lang, _ in i18n.LANGUAGES:
                app.set_language(lang)
                self.pump(root, 0.2)
            for name in theme.THEMES:
                app.set_theme(name)
                self.pump(root, 0.2)
            self.assertEqual(errors, [])
        finally:
            root.destroy()

    def test_limited_mode(self):
        root, app, errors = self.open_app(admin=False)
        try:
            self.assertEqual(len(self.dialogs(root)), 1, "the administrator dialog must open")
            for dialog in self.dialogs(root):
                dialog.destroy()
            admin_tweak = next(t for t in tweaks.TWEAKS if t.admin and app.status_map()[t.id] != "unavailable")
            self.assertEqual(app.card_state(admin_tweak), "admin")
            self.assertFalse(app.selectable(admin_tweak))
            self.assertEqual(engine.list_snapshots(), [], "no original-state snapshot without administrator rights")
            self.check_every_page(root, app)
            self.assertEqual(errors, [])
        finally:
            root.destroy()

    def test_memory_limiter_and_tray(self):
        root, app, errors = self.open_app(admin=True)
        destroyed = False
        try:
            for dialog in self.dialogs(root):
                dialog.destroy()
            app.show_page("memory")
            deadline = time.time() + 30
            while app.installed is None and time.time() < deadline:  # programs are found in the background
                self.pump(root, 0.1)
            self.assertIsInstance(app.installed, list)
            self.pump(root, 0.3)
            if len(app.installed) > main.INSTALLED_VISIBLE:
                app.toggle_installed()
                self.pump(root, 0.3)
            self.assertFalse(app.limiter.active())
            self.assertIsNone(app.tray, "no tray icon while the limiter is off")
            # A program name no process has: the limiter has nothing to change
            app.add_rule("simpletool-test-absent.exe", 700)
            app.add_rule("explorer.exe", 700)  # a system process cannot be added
            rules = app.limiter.snapshot()["config"]["rules"]
            self.assertEqual([r["name"] for r in rules], ["simpletool-test-absent"])
            app.change_rule("simpletool-test-absent", title="Test program")
            app.rebuild_memory()
            self.pump(root, 0.3)
            self.pump(root, 0.3)
            app.mem["toggle"]._click(None)
            self.pump(root, 0.3)
            self.assertTrue(app.limiter.active())
            self.assertTrue(app.tray.visible(), "the tray icon shows while the limiter works")
            self.assertEqual(app.nav["memory"]["count"].cget("text"), "1")
            # The close button hides the window to the tray, Open in the icon menu brings it back
            app.on_close()
            self.pump(root, 0.2)
            self.assertTrue(app.hidden)
            self.assertEqual(root.state(), "withdrawn")
            app.on_tray_command(main.TRAY_OPEN)
            self.pump(root, 0.2)
            self.assertFalse(app.hidden)
            self.assertEqual(root.state(), "normal")
            # Exiting is not allowed while tweaks are being applied
            app.acting = True
            app.on_tray_command(main.TRAY_EXIT)
            self.pump(root, 0.2)
            self.assertTrue(root.winfo_exists())
            app.acting = False
            for lang, _ in i18n.LANGUAGES:
                app.set_language(lang)
                self.pump(root, 0.2)
            self.assertEqual(errors, [])
            tray_icon, worker = app.tray, app.limiter._thread
            app.on_tray_command(main.TRAY_EXIT)
            destroyed = True
            self.assertFalse(tray_icon.visible())
            self.assertFalse(worker.is_alive(), "the limiter stops with the window")
        finally:
            if not destroyed:
                root.destroy()


if __name__ == "__main__":
    unittest.main()
