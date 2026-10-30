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

import diagnostics
import engine
import i18n
import limiter
import main
import terms
import theme
import tweaks
import uninstaller
import updater
import updates
from tests.test_diagnostics import event, healthy
from widgets import GradientButton

PROFILE = r"C:\Users\A"  # a made-up user profile for the tests, secret-scan: allow


def forbidden(*args, **kwargs):
    raise AssertionError("the UI test must never change the system")


class UiSmoke(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="simpletool-ui-test-")
        # No pop-up notifications, the terms are already accepted
        self.settings = {"lang": "en", "theme": "navy", "tray_hint_shown": True, "terms": terms.VERSION,
                         "seen_version": main.VERSION,
                         "update_checked": datetime.datetime.now(datetime.timezone.utc).isoformat()}
        self.other_account = None
        self.opened = []  # addresses SimpleTool asked Windows to open: a website, an email
        self.started = []  # Windows tools troubleshooting opened
        # Troubleshooting reads made-up facts: a PC with a few problems, read at once
        self.facts = healthy()
        self.facts.update(cpu={"load": 91.0, "top": [("game.exe", 80.0)]}, startup=[f"App {i}" for i in range(14)],
                          events=[event("Microsoft-Windows-Kernel-Power", 41, level=1, args=["0"])],
                          devices=[{"name": "Wi-Fi adapter", "code": 28}], restart_pending=None)
        # Programs: made-up entries; the icon and the "uninstaller" of the first are an existing Windows file
        self.notepad = notepad = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "notepad.exe")
        uninstall = r"HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"
        self.good_folder = os.path.join(self.tmp, "Good Tool")  # its install folder, for "Open file location"
        os.makedirs(self.good_folder)
        self.programs = [
            uninstaller.Program(r"HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall\GoodTool", "Good Tool",
                                "Acme", "2.1", 5 * 2 ** 20, datetime.date(2026, 10, 1), location=self.good_folder,
                                icon=(notepad, 0), uninstall=f'"{notepad}" /uninstall', user=True),
            uninstaller.Program(uninstall + r"\Edge", "Microsoft Edge", "Microsoft Corporation", "130.0",
                                removable=False),
            uninstaller.Program(uninstall + r"\OldTool", "Old Tool", size=40 * 2 ** 20,
                                uninstall=r'"C:\nowhere-at-all\unins000.exe"'),
        ]
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
            mock.patch.object(main.App, "shell_open", lambda app, target, args=None:
                              self.started.append((target, args)) or True),
            mock.patch.object(diagnostics, "gather", self.fake_gather),
            mock.patch.object(uninstaller, "installed_programs", lambda: list(self.programs)),
            mock.patch.object(uninstaller, "find_leftovers", lambda program, others=(): []),
            mock.patch.object(uninstaller, "run_uninstaller", forbidden),
            mock.patch.object(uninstaller, "remove_leftovers", forbidden),
            mock.patch.object(uninstaller, "to_recycle_bin", forbidden),
        ]
        for patch in self.patches:
            patch.start()

    def fake_gather(self, report=lambda step: None, api=None):
        for group in diagnostics.GROUPS:
            report(group)
        return dict(self.facts)

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
            if page == "diagnostics":  # the first visit starts the check: its results are shown a moment later
                self.wait(root, lambda: app.diag is not None and app.diag_cards)
            for key, widgets in list(app.cards.items()) + [(k, w) for k, w in app.service_cards.items()]:
                kind = "t" if key in app.cards else "s"
                app.toggle_details((kind, key), widgets)
            for check, widgets in app.diag_cards.items():
                app.toggle_details(("d", check), widgets)
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

    def test_daily_update_check(self):
        ui = i18n.TEXTS["en"]["ui"]
        del self.settings["update_checked"]  # never checked: due now
        newer = {"version": "9.9", "newer": True, "url": None, "page": None, "sha256": None, "size": None}
        asked = []
        root, app, errors = self.open_app(admin=True)
        try:
            with mock.patch.object(updates, "check", lambda current: asked.append(current) or newer):
                app.daily_update_check()
                self.wait(root, lambda: not app.checking_updates)
                self.pump(root, 0.1)
                self.assertEqual(asked, [main.VERSION])
                self.assertEqual(app.help_badge.cget("text"), "●", "a dot on Help, no window")
                self.assertEqual(self.dialogs(root), [])
                self.assertIn("update_checked", self.settings)
                menu = app.help_menu()
                labels = [menu.entrycget(i, "label") for i in range(menu.index("end") + 1)
                          if menu.type(i) != "separator"]
                self.assertIn("● " + ui["update_install_menu"].format(version="9.9"), labels)
                app.daily_update_check()  # checked a moment ago: not again today
                self.pump(root, 0.2)
                self.assertEqual(len(asked), 1)
                app.set_daily_check(False)
                del self.settings["update_checked"]
                app.daily_update_check()
                self.pump(root, 0.2)
                self.assertEqual(len(asked), 1, "turned off in Help")
            self.assertEqual(errors, [])
        finally:
            root.destroy()

    def test_update_in_one_click(self):
        ui = i18n.TEXTS["en"]["ui"]
        info = {"version": "9.9", "newer": True, "url": updater.RELEASES + "v9.9/SimpleTool.exe", "page": None,
                "sha256": "a" * 64, "size": 10}
        started = []
        exe = "C:/Tools/SimpleTool.exe"
        root, app, errors = self.open_app(admin=True)
        try:
            with mock.patch.object(updater, "can_install", lambda i: True), \
                    mock.patch.object(updater, "install", lambda i, progress: (progress(5, 10), exe)[1]), \
                    mock.patch.object(updater, "start", started.append):
                # It fails first: the window says so, and the running version stays
                with mock.patch.object(updater, "install", mock.Mock(side_effect=updater.UpdateFailed("no space"))):
                    app.show_update(info)
                    self.button(self.dialogs(root)[0], ui["update_install"])._click(None)
                    self.wait(root, lambda: self.dialogs(root))
                self.assertEqual(self.dialogs(root)[0].title(), ui["update_install_failed_title"])
                self.assertEqual(started, [])
                for dialog in self.dialogs(root):
                    dialog.destroy()
                app.show_update(info)
                self.button(self.dialogs(root)[0], ui["update_install"])._click(None)
                self.wait(root, lambda: started)
                self.pump(root, 0.2)
            self.assertEqual(started, [exe])
            with self.assertRaises(tk.TclError):
                root.winfo_exists()  # this copy exits for the new one
        finally:
            try:
                root.destroy()
            except tk.TclError:
                pass

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

    def test_troubleshooting(self):
        ui = i18n.TEXTS["en"]["ui"]
        root, app, errors = self.open_app(admin=False)
        try:
            for dialog in self.dialogs(root):
                dialog.destroy()
            self.assertIsNone(app.diag, "the check waits until its page is opened")
            self.assertEqual(app.nav["diagnostics"]["count"].cget("text"), "")
            app.show_page("diagnostics")
            self.pump(root, 0.1)
            self.assertTrue(app.diag_running)
            self.assertEqual(app.message_label.cget("text"), ui["diag_running"])
            self.wait(root, lambda: not app.diag_running and app.diag_cards)
            found = {f.check: f.severity for f in app.diag if f.severity != "ok"}
            self.assertEqual(found, {"cpu_load": "warning", "startup_apps": "warning", "crashes": "warning",
                                     "devices": "warning", "pending_restart": "unknown"})
            self.assertEqual(app.nav["diagnostics"]["count"].cget("text"), "4")
            self.assertEqual(set(app.diag_cards), {f.check for f in app.diag})
            # Details show the explanation, the lines and the buttons; a button opens its Windows tool
            app.toggle_details(("d", "devices"), app.diag_cards["devices"])
            self.pump(root, 0.5)
            inner = app.diag_cards["devices"]["inner"]
            self.button(inner, ui["act_devices"])._click(None)
            self.assertEqual(self.started, [("devmgmt.msc", None)])
            app.toggle_details(("d", "cpu_load"), app.diag_cards["cpu_load"])
            self.pump(root, 0.5)
            self.click_text(app.diag_cards["cpu_load"]["inner"], "game.exe — 80%")
            # A suggestion inside SimpleTool goes to its page
            app.toggle_details(("d", "ram_load"), app.diag_cards["ram_load"])
            self.pump(root, 0.5)
            self.button(app.diag_cards["ram_load"]["inner"], ui["act_memory"])._click(None)
            self.pump(root, 0.2)
            self.assertEqual(app.page, "memory")
            # Scan again reads the system once more; another language keeps the results
            self.facts["cpu"] = {"load": 5.0, "top": []}
            app.show_page("diagnostics")
            app.rescan_diagnostics()
            self.assertIsNone(app.diag)
            self.wait(root, lambda: not app.diag_running and app.diag_cards)
            self.assertEqual(app.nav["diagnostics"]["count"].cget("text"), "3")
            for lang, _ in i18n.LANGUAGES:
                app.set_language(lang)
                self.pump(root, 0.2)
                self.assertTrue(app.diag_cards)
            for name in theme.THEMES:
                app.set_theme(name)
                self.pump(root, 0.2)
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

    def shown_programs(self, app):
        """The names of the program cards on the Programs page, top to bottom."""
        cards = {card: program.name for program, card in app.program_rows}
        return [cards[w] for w in app.list_frame.pack_slaves() if w in cards]

    def program_card(self, app, name):
        return next(card for program, card in app.program_rows if program.name == name)

    def texts(self, parent):
        return [w.cget("text") for w in self.widgets(parent) if isinstance(w, tk.Label)]

    def open_programs(self, admin):
        root, app, errors = self.open_app(admin=admin)
        for dialog in self.dialogs(root):  # the administrator dialog of the limited mode
            dialog.destroy()
        app.show_page("programs", animate=False)
        self.wait(root, lambda: app.program_rows)
        return root, app, errors

    def test_programs(self):
        ui = i18n.TEXTS["en"]["ui"]
        root, app, errors = self.open_programs(admin=True)
        try:
            self.assertEqual(self.shown_programs(app), ["Good Tool", "Microsoft Edge", "Old Tool"])
            self.assertEqual(app.nav["programs"]["count"].cget("text"), "3")
            self.assertIn(self.programs[0].key, app.program_icons, "its own icon")
            # "Open file location": the folder of a program whose place is known; none for one whose place is not
            good = self.program_card(app, "Good Tool")
            self.assertNotIn(ui["prog_location"], self.texts(self.program_card(app, "Microsoft Edge")))
            self.click_text(good, ui["prog_location"])
            self.assertEqual(self.started[-1], (self.good_folder, None))
            self.assertEqual(app.program_count.cget("text"),
                             ui["prog_count"].format(n=3, size=app.size_text(45 * 2 ** 20)))
            edge = self.program_card(app, "Microsoft Edge")
            self.assertIn(ui["prog_not_removable"], self.texts(edge))
            self.assertFalse([w for w in self.widgets(edge) if isinstance(w, GradientButton)], "no button")
            self.button(self.program_card(app, "Old Tool"), ui["prog_clean_up"])
            # Search and order work on the cards already built
            app.program_search.set("acme")
            self.assertEqual(self.shown_programs(app), ["Good Tool"])
            self.assertEqual(app.program_count.cget("text"), ui["prog_found"].format(n=1, total=3))
            app.program_search.set("")
            app.sort_programs("size")
            self.assertEqual(self.shown_programs(app), ["Old Tool", "Good Tool", "Microsoft Edge"])
            app.sort_programs("name")
            # Uninstalling: a question first, the restore point check, the uninstaller, then what it left
            recent = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=3)
            calls, removed = [], []
            leftovers = [{"kind": "folder", "path": rf"{PROFILE}\AppData\Roaming\Good Tool", "name": "", "size": 2048},
                         {"kind": "key", "path": r"HKCU\Software\Good Tool", "name": "", "size": 0}]

            def run(program):
                calls.append(("run", program.name))
                self.programs.remove(program)
                return 0

            def find(program, others):
                calls.append(("find", sorted(p.name for p in others)))
                return leftovers

            self.button(self.program_card(app, "Good Tool"), ui["prog_uninstall"])._click(None)
            dialog = self.dialogs(root)[0]
            self.assertEqual(dialog.title(), ui["prog_confirm_title"])
            with mock.patch.object(engine, "recent_restore_point", lambda: recent), \
                    mock.patch.object(uninstaller, "run_uninstaller", run), \
                    mock.patch.object(uninstaller, "still_installed", lambda program: False), \
                    mock.patch.object(uninstaller, "find_leftovers", find):
                self.button(dialog, ui["prog_uninstall"])._click(None)
                self.wait(root, lambda: self.dialogs(root) and self.dialogs(root)[0].title() == ui["prog_left_title"])
            self.assertEqual(calls, [("run", "Good Tool"), ("find", ["Microsoft Edge", "Old Tool"])])
            # Everything is ticked; what is unticked stays
            dialog = self.dialogs(root)[0]
            self.click_text(dialog, r"HKCU\Software\Good Tool")
            with mock.patch.object(uninstaller, "remove_leftovers",
                                   lambda program, items: removed.append(items) or (self.tmp, [])):
                self.button(dialog, ui["prog_left_remove"])._click(None)
                self.wait(root, lambda: removed and not app.busy)
            self.assertEqual(removed, [leftovers[:1]])
            self.assertIn(ui["prog_left_done"].format(n=1), self.texts(app.toaster.card))
            # The list is read again: the program is gone
            self.wait(root, lambda: not app.programs_loading and len(app.programs) == 2 and app.program_rows)
            self.assertEqual(self.shown_programs(app), ["Microsoft Edge", "Old Tool"])
            # An entry whose uninstaller is gone: only the leftovers are looked for, nothing is run (tripwire)
            self.button(self.program_card(app, "Old Tool"), ui["prog_clean_up"])._click(None)
            dialog = self.dialogs(root)[0]
            self.assertIn(ui["prog_confirm_missing"], self.texts(dialog))
            with mock.patch.object(engine, "recent_restore_point", lambda: recent), \
                    mock.patch.object(uninstaller, "find_leftovers", lambda program, others: []):
                self.button(dialog, ui["prog_clean_up"])._click(None)
                self.wait(root, lambda: not app.busy and not self.dialogs(root))
            self.assertIn(ui["prog_clean"].format(name="Old Tool"), self.texts(app.toaster.card))
            self.wait(root, lambda: not app.programs_loading)  # the list is read again after each removal
            # The uninstaller was cancelled: the program stays, nothing is looked for
            self.programs[:] = [uninstaller.Program("k", "Kept Tool", uninstall=f'"{self.notepad}" /uninstall',
                                                    user=True)]
            app.load_programs(force=True)
            self.wait(root, lambda: not app.programs_loading and self.shown_programs(app) == ["Kept Tool"])
            self.button(self.program_card(app, "Kept Tool"), ui["prog_uninstall"])._click(None)
            with mock.patch.object(engine, "recent_restore_point", lambda: recent), \
                    mock.patch.object(uninstaller, "run_uninstaller", lambda program: 1602), \
                    mock.patch.object(uninstaller, "still_installed", lambda program: True):
                self.button(self.dialogs(root)[0], ui["prog_uninstall"])._click(None)
                self.wait(root, lambda: not app.busy and not self.dialogs(root))
            self.assertIn(ui["prog_kept"].format(name="Kept Tool"), self.texts(app.toaster.card))
            # Every language and theme on this page
            for lang, _ in i18n.LANGUAGES:
                app.set_language(lang)
                self.pump(root, 0.2)
            for name in theme.THEMES:
                app.set_theme(name)
                self.pump(root, 0.2)
            self.assertEqual(errors, [])
        finally:
            root.destroy()

    def test_leftovers_of_programs_removed_without_simpletool(self):
        ui = i18n.TEXTS["en"]["ui"]
        root, app, errors = self.open_programs(admin=True)  # SimpleTool keeps the list it read
        try:
            recent = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=3)
            # Two programs are removed through Windows' settings; one of them left a folder
            old = self.programs.pop(2)
            edge = self.programs.pop(1)
            left = {old.key: [{"kind": "folder", "path": rf"{PROFILE}\AppData\Roaming\Old Tool", "name": "",
                               "size": 4096}],
                    edge.key: [{"kind": "key", "path": r"HKCU\Software\Edge Helper", "name": "", "size": 0}]}
            # Stopped by tearDown before the patches of setUp, so that the real search comes back
            finding = mock.patch.object(uninstaller, "find_leftovers",
                                        lambda program, others: left.get(program.key, []))
            self.patches.append(finding)
            finding.start()
            app.load_programs(force=True)
            self.wait(root, lambda: not app.programs_loading and len(app.programs_gone) == 2)
            self.assertIn(ui["prog_gone_title"], self.texts(app.list_frame))
            self.assertEqual(self.shown_programs(app), ["Good Tool"])
            # What one left is shown first, and removed after the restore point check
            removed = []
            buttons = [w for w in self.widgets(app.list_frame) if isinstance(w, GradientButton)
                       and w.itemcget(w.text, "text") == ui["prog_clean_up"]]
            self.assertEqual(len(buttons), 2)
            card = next(card for card in app.page_cards if old.name in self.texts(card))
            self.button(card, ui["prog_clean_up"])._click(None)
            dialog = self.dialogs(root)[0]
            self.assertEqual(dialog.title(), ui["prog_left_title"])
            with mock.patch.object(engine, "recent_restore_point", lambda: recent), \
                    mock.patch.object(uninstaller, "remove_leftovers",
                                      lambda program, items: removed.append((program.name, items)) or (self.tmp, [])):
                self.button(dialog, ui["prog_left_remove"])._click(None)
                self.wait(root, lambda: removed and not app.busy and not app.programs_loading)
            self.assertEqual(removed, [("Old Tool", left[old.key])])
            self.assertEqual([entry[0].name for entry in app.programs_gone], ["Microsoft Edge"])
            # The other one: the user keeps what it left, and it is not offered again
            self.click_text(app.list_frame, ui["prog_gone_hide"])
            self.assertEqual(app.programs_gone, [])
            self.assertNotIn(ui["prog_gone_title"], self.texts(app.list_frame))
            app.load_programs(force=True)
            self.wait(root, lambda: not app.programs_loading)
            self.assertEqual(app.programs_gone, [])
            self.assertEqual(errors, [])
        finally:
            root.destroy()

    def test_several_programs_at_once(self):
        ui = i18n.TEXTS["en"]["ui"]
        root, app, errors = self.open_programs(admin=True)
        try:
            recent = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=3)
            good, edge, old = self.programs
            # Ticked by the check box or the name; Edge cannot be removed, so it cannot be ticked
            self.assertFalse(app.program_boxes[edge.key].enabled)
            self.click_text(self.program_card(app, "Good Tool"), "Good Tool")
            app.program_boxes[old.key].event_generate("<Button-1>")
            self.assertEqual(app.program_selected, {good.key, old.key})
            self.assertIn(ui["prog_selected"].format(n=2) + "  ·  " + app.size_text(45 * 2 ** 20),
                          self.texts(app.list_frame))
            calls, removed = [], []
            left = {good.key: [{"kind": "folder", "path": rf"{PROFILE}\AppData\Roaming\Good Tool", "name": "",
                                "size": 2048}],
                    old.key: [{"kind": "key", "path": r"HKCU\Software\Old Tool", "name": "", "size": 0},
                              {"kind": "folder", "path": rf"{PROFILE}\AppData\Local\Old Tool", "name": "",
                               "size": 4096}]}

            def run(program):
                calls.append(program.name)
                self.programs.remove(program)
                return 0

            self.button(app.list_frame, ui["prog_batch_remove"])._click(None)
            dialog = self.dialogs(root)[0]
            self.assertEqual(dialog.title(), ui["prog_batch_title"])
            self.assertTrue({"Good Tool", "Old Tool"} <= set(self.texts(dialog)))
            done = ui["prog_batch_finished"].format(removed=2, n=2)
            with mock.patch.object(engine, "recent_restore_point", lambda: recent), \
                    mock.patch.object(uninstaller, "run_uninstaller", run), \
                    mock.patch.object(uninstaller, "still_installed", lambda program: False), \
                    mock.patch.object(uninstaller, "find_leftovers", lambda program, others: left.get(program.key, [])):
                self.button(dialog, ui["prog_batch_go"].format(n=2))._click(None)
                self.wait(root, lambda: self.dialogs(root) and done in self.texts(self.dialogs(root)[0]))
            self.assertEqual(calls, ["Good Tool"], "the uninstaller of Old Tool is gone: only its leftovers")
            progress = self.dialogs(root)[0]
            self.assertEqual(self.texts(progress).count(ui["prog_state_removed"]), 2)
            # Everything both left, in one list; what is unticked stays
            self.button(progress, ui["prog_batch_next"])._click(None)
            dialog = self.dialogs(root)[0]
            self.assertIn(ui["prog_batch_left_heading"].format(n=2), self.texts(dialog))
            self.click_text(dialog, r"HKCU\Software\Old Tool")
            with mock.patch.object(uninstaller, "remove_leftovers",
                                   lambda program, items: removed.append((program.name, items)) or (self.tmp, [])):
                self.button(dialog, ui["prog_left_remove"])._click(None)
                self.wait(root, lambda: removed and not app.busy and not app.programs_loading)
            self.assertEqual(removed, [("Good Tool", left[good.key]), ("Old Tool", left[old.key][1:])])
            self.assertEqual(app.program_selected, set())
            self.assertEqual(errors, [])
        finally:
            root.destroy()

    def test_the_programs_page_keeps_its_place(self):
        # Reading the list again (after an uninstall) does not throw the page back to its top
        self.programs += [uninstaller.Program(f"k{i}", f"Tool {i:02}", uninstall=f'"{self.notepad}"', user=True)
                          for i in range(40)]
        root, app, errors = self.open_programs(admin=True)
        try:
            app.canvas.yview_moveto(0.5)
            self.pump(root, 0.2)
            top = app.canvas.canvasy(0)
            self.assertGreater(top, 0)
            app.load_programs(force=True)
            self.wait(root, lambda: not app.programs_loading)
            self.pump(root, 0.3)
            self.assertAlmostEqual(app.canvas.canvasy(0), top, delta=app.px(4))
            self.assertEqual(errors, [])
        finally:
            root.destroy()

    def test_programs_without_administrator_rights(self):
        ui = i18n.TEXTS["en"]["ui"]
        root, app, errors = self.open_programs(admin=False)
        try:
            self.assertIn(ui["prog_admin"], self.texts(app.list_frame))
            # Installed for this account only: it can go; installed for every account: it needs the rights
            self.assertTrue(self.button(self.program_card(app, "Good Tool"), ui["prog_uninstall"]).enabled)
            self.assertFalse(self.button(self.program_card(app, "Old Tool"), ui["prog_clean_up"]).enabled)
            # Windows creates restore points only for administrators: the dialog says so, for a program
            self.button(self.program_card(app, "Good Tool"), ui["prog_uninstall"])._click(None)
            self.button(self.dialogs(root)[0], ui["prog_uninstall"])._click(None)
            self.pump(root, 0.1)
            dialog = self.dialogs(root)[0]
            self.assertEqual(dialog.title(), ui["rp_gate_title"])
            self.assertIn(ui["rp_gate_admin_text_programs"], self.texts(dialog))
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
