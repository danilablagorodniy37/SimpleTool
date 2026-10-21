"""The SimpleTool window: every page, details, language and theme opens without errors, the column is aligned.

The scan reads the real system (read-only). Apply, revert, snapshot restore, restore points and
any change to process memory are blocked by a tripwire during the test: the window cannot change anything.
Nothing goes online either: the update check and opened addresses are replaced.
"""
import datetime
import json
import os
import shutil
import tempfile
import time
import tkinter as tk
import unittest
import urllib.parse
from unittest import mock

import engine
import i18n
import limiter
import main
import terms
import theme
import tweaks
import updates
from widgets import GradientButton


def forbidden(*args, **kwargs):
    raise AssertionError("the UI test must never change the system")


class UiSmoke(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="simpletool-ui-test-")
        # No pop-up notifications, the terms are already accepted
        self.settings = {"lang": "en", "theme": "navy", "tray_hint_shown": True, "terms": terms.VERSION,
                         "seen_version": main.VERSION}
        self.other_account = None
        self.opened = []  # addresses SimpleTool asked Windows to open: a website, an email
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
            mock.patch.object(engine, "other_account", lambda: self.other_account),
            mock.patch.object(engine, "recent_restore_point", lambda: None),
            mock.patch.object(updates, "check", forbidden),
            mock.patch.object(main.App, "open_url", lambda app, url: self.opened.append(url) or True),
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
            root.geometry("1080x740+40+40")
            app = main.App(root)
        # Errors are collected instead of being shown in a window and written to error.log
        app.report_error = lambda kind, value, tb: errors.append(f"{kind.__name__}: {value}")
        root.report_callback_exception = app.report_error
        deadline = time.time() + 30
        while app.busy and time.time() < deadline:
            self.pump(root, 0.1)
        self.assertFalse(app.busy, "the scan did not finish")
        self.pump(root, 0.5)
        return root, app, errors

    def dialogs(self, root):
        return [w for w in root.winfo_children() if isinstance(w, tk.Toplevel)]

    def widgets(self, parent):
        for child in parent.winfo_children():
            yield child
            yield from self.widgets(child)

    def button(self, dialog, text):
        """The button with this text in a dialog."""
        found = [w for w in self.widgets(dialog) if isinstance(w, GradientButton) and w.itemcget(w.text, "text") == text]
        self.assertEqual(len(found), 1, f"button {text!r}")
        return found[0]

    def click_text(self, dialog, text):
        """Clicks a link or label with this text."""
        found = [w for w in self.widgets(dialog) if isinstance(w, tk.Label) and w.cget("text") == text]
        self.assertEqual(len(found), 1, f"label {text!r}")
        found[0].event_generate("<Button-1>")

    def wait(self, root, condition, seconds=10):
        deadline = time.time() + seconds
        while not condition() and time.time() < deadline:
            self.pump(root, 0.05)
        self.assertTrue(condition(), "timed out")

    def press_apply(self, root, app):
        """Selects one tweak that is not applied yet and presses Apply. Returns the list Apply would act on."""
        started = []
        app.start_work = lambda chosen, *args: started.append([t.id for t in chosen])
        tweak = next(t for t in tweaks.TWEAKS if app.selectable(t) and app.card_state(t) in ("not_applied", "partial"))
        app.show_page(tweak.category, animate=False)  # its card must be on screen to be selected
        self.pump(root, 0.1)
        app.toggle_select(tweak)
        app.apply_selected()
        self.wait(root, lambda: started or self.dialogs(root))
        self.pump(root, 0.1)
        return started, tweak

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

    def test_terms_on_first_run(self):
        del self.settings["terms"]
        root, app, errors = self.open_app(admin=False)
        try:
            self.assertEqual(len(self.dialogs(root)), 1, "only the terms: the administrator dialog waits for them")
            self.assertEqual(self.dialogs(root)[0].title(), terms.TERMS["en"]["title"])
            app.reopen_terms(self.dialogs(root)[0], "uk", True)  # the terms in another language
            self.pump(root, 0.2)
            self.assertEqual([d.title() for d in self.dialogs(root)], [terms.TERMS["uk"]["title"]])
            app.accept_terms(self.dialogs(root)[0])
            self.pump(root, 0.2)
            self.assertEqual(self.settings["terms"], terms.VERSION)
            self.assertEqual([d.title() for d in self.dialogs(root)], [i18n.TEXTS["uk"]["ui"]["admin_title"]])
            self.assertEqual(errors, [])
        finally:
            root.destroy()

    def test_whats_new_after_an_update(self):
        ui = i18n.TEXTS["en"]["ui"]
        del self.settings["seen_version"]  # 0.6.1 did not record its version: an update from it
        root, app, errors = self.open_app(admin=False)
        try:
            self.assertEqual([d.title() for d in self.dialogs(root)], [ui["whatsnew_link"]],
                             "What's new first, alone")
            self.assertEqual(self.settings["seen_version"], main.VERSION, "shown once")
            self.button(self.dialogs(root)[0], ui["whatsnew_ok"])._click(None)
            self.pump(root, 0.4)
            self.assertEqual([d.title() for d in self.dialogs(root)], [ui["admin_title"]], "then the next window")
            for dialog in self.dialogs(root):
                dialog.destroy()
            app.show_whats_new()  # Help → What's new
            self.pump(root, 0.2)
            self.assertEqual([d.title() for d in self.dialogs(root)], [ui["whatsnew_link"]])
            self.assertEqual(errors, [])
        finally:
            root.destroy()

    def test_no_whats_new_on_a_first_run(self):
        del self.settings["seen_version"]
        del self.settings["terms"]
        root, app, errors = self.open_app(admin=True)
        try:
            app.accept_terms(self.dialogs(root)[0])
            self.pump(root, 0.3)
            self.assertEqual(self.dialogs(root), [], "a new user has nothing to compare with")
            self.assertEqual(self.settings["seen_version"], main.VERSION)
        finally:
            root.destroy()

    def test_declining_the_terms_exits(self):
        del self.settings["terms"]
        root, app, errors = self.open_app(admin=True)
        dialog = self.dialogs(root)[0]
        root.tk.call(dialog.protocol("WM_DELETE_WINDOW"))  # the close button of the terms window
        self.assertNotIn("terms", self.settings)
        with self.assertRaises(tk.TclError):
            root.winfo_exists()

    def test_another_account_is_reported(self):
        self.other_account = ("Admin", "Child")
        root, app, errors = self.open_app(admin=True)
        try:
            self.assertEqual([d.title() for d in self.dialogs(root)], [i18n.TEXTS["en"]["ui"]["other_account_title"]])
            self.assertEqual(errors, [])
        finally:
            root.destroy()

    def test_apply_after_a_recent_restore_point(self):
        root, app, errors = self.open_app(admin=True)
        try:
            recent = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=3)
            with mock.patch.object(engine, "recent_restore_point", lambda: recent):
                started, tweak = self.press_apply(root, app)
            self.assertEqual(started, [[tweak.id]])
            self.assertEqual(self.dialogs(root), [])
            self.assertEqual(errors, [])
        finally:
            root.destroy()

    def test_apply_creates_a_restore_point_first(self):
        ui = i18n.TEXTS["en"]["ui"]
        root, app, errors = self.open_app(admin=True)
        try:
            started, tweak = self.press_apply(root, app)
            self.assertEqual(started, [], "nothing is applied before the restore point")
            dialog = self.dialogs(root)[0]
            self.assertEqual(dialog.title(), ui["rp_gate_title"])
            # Windows refuses: the dialog comes back with its reason, and Apply still waits
            with mock.patch.object(engine, "create_restore_point", lambda: (False, "Turned off by policy", False)):
                self.button(dialog, ui["rp_gate_create"])._click(None)
                self.wait(root, lambda: self.dialogs(root) and not app.busy)
            dialog = self.dialogs(root)[0]
            texts = " ".join(w.cget("text") for w in self.widgets(dialog) if isinstance(w, tk.Label))
            self.assertIn("Turned off by policy", texts)
            self.assertEqual(started, [])
            with mock.patch.object(engine, "create_restore_point", lambda: (True, "", True)):
                self.button(dialog, ui["rp_gate_create"])._click(None)
                self.wait(root, lambda: started)
            self.assertEqual(started, [[tweak.id]])
            self.assertEqual(errors, [])
        finally:
            root.destroy()

    def test_apply_without_a_restore_point_needs_the_tick(self):
        ui = i18n.TEXTS["en"]["ui"]
        root, app, errors = self.open_app(admin=True)
        try:
            started, tweak = self.press_apply(root, app)
            self.click_text(self.dialogs(root)[0], ui["rp_gate_skip"])
            self.pump(root, 0.2)
            dialog = self.dialogs(root)[0]
            self.assertEqual(dialog.title(), ui["rp_skip_title"])
            apply = self.button(dialog, ui["rp_skip_apply"])
            self.assertFalse(apply.enabled, "the button works only after the tick")
            apply._click(None)
            self.assertEqual(started, [])
            self.click_text(dialog, ui["rp_skip_confirm"])
            self.assertTrue(apply.enabled)
            apply._click(None)
            self.pump(root, 0.1)
            self.assertEqual(started, [[tweak.id]])
            self.assertEqual(self.dialogs(root), [])
            self.assertEqual(errors, [])
        finally:
            root.destroy()

    def test_limited_mode_asks_for_administrator_rights_before_apply(self):
        ui = i18n.TEXTS["en"]["ui"]
        root, app, errors = self.open_app(admin=False)
        try:
            for dialog in self.dialogs(root):
                dialog.destroy()
            started, tweak = self.press_apply(root, app)
            self.assertEqual(started, [])
            dialog = self.dialogs(root)[0]
            self.assertEqual(dialog.title(), ui["rp_gate_title"])
            self.button(dialog, ui["admin_restart"])  # restarting is the way to a restore point
            self.assertEqual(errors, [])
        finally:
            root.destroy()

    def test_update_check(self):
        ui = i18n.TEXTS["en"]["ui"]
        exe = "https://github.com/danilablagorodniy37/SimpleTool/releases/download/v9.9/SimpleTool.exe"
        root, app, errors = self.open_app(admin=True)
        try:
            newer = {"version": "9.9", "newer": True, "url": exe, "page": None}
            with mock.patch.object(updates, "check", lambda current: newer):
                app.check_updates()
                self.wait(root, lambda: self.dialogs(root))
            dialog = self.dialogs(root)[0]
            self.assertEqual(dialog.title(), ui["update_title"])
            self.button(dialog, ui["update_download"])._click(None)
            self.assertEqual(self.opened, [exe])

            def offline(current):
                raise updates.CheckFailed("getaddrinfo failed")

            with mock.patch.object(updates, "check", offline):
                app.check_updates()
                self.wait(root, lambda: self.dialogs(root))
            dialog = self.dialogs(root)[0]
            self.assertEqual(dialog.title(), ui["update_failed_title"])
            self.button(dialog, ui["update_open_site"])._click(None)
            self.assertEqual(self.opened[-1], updates.PAGES["en"])

            with mock.patch.object(updates, "check", lambda current: dict(newer, newer=False)):
                app.check_updates()
                self.wait(root, lambda: not app.checking_updates)
            self.pump(root, 0.1)
            self.assertEqual(self.dialogs(root), [], "the latest version is only a notification")
            self.assertEqual(errors, [])
        finally:
            root.destroy()

    def test_report_a_problem(self):
        ui = i18n.TEXTS["en"]["ui"]
        root, app, errors = self.open_app(admin=True)
        try:
            app.show_report()
            dialog = self.dialogs(root)[0]
            self.assertEqual(dialog.title(), ui["report_title"])
            shown = [w.get("1.0", "end").strip() for w in self.widgets(dialog) if isinstance(w, tk.Text)]
            self.button(dialog, ui["report_write"])._click(None)
            self.assertTrue(self.opened[-1].startswith(f"mailto:{main.SUPPORT_EMAIL}?subject=SimpleTool%20"))
            self.assertIn(main.VERSION, self.opened[-1])
            # The letter carries the specifications the window showed
            body = urllib.parse.unquote(self.opened[-1].split("body=", 1)[1])
            self.assertTrue(shown and "Processor: " in shown[0] and shown[0] in body, body)
            self.assertEqual(errors, [])
        finally:
            root.destroy()

    def test_deleting_a_snapshot_asks_first(self):
        ui = i18n.TEXTS["en"]["ui"]
        path = os.path.join(engine.snapshots_dir(), "manual-test.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"kind": "manual", "created": "2026-10-20T12:00:00", "tweaks": {}}, f)
        root, app, errors = self.open_app(admin=True)
        try:
            data = next(d for p, d in app.snapshots if p == path)
            app.confirm_delete(path, data)
            dialog = self.dialogs(root)[0]
            self.assertEqual(dialog.title(), ui["snap_delete_title"])
            self.assertTrue(os.path.exists(path), "nothing is deleted before the answer")
            self.button(dialog, ui["snap_delete_ok"])._click(None)
            self.assertFalse(os.path.exists(path))
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
