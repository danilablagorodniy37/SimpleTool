"""Окно SimpleTool: все разделы, подробности, языки и темы открываются без ошибок, колонка выровнена.

Сканирование читает настоящую систему (только чтение). Применение, откат, восстановление снимков и
точки восстановления на время теста заблокированы растяжкой: окно не может ничего изменить.
"""
import shutil
import tempfile
import time
import tkinter as tk
import unittest
from unittest import mock

import engine
import i18n
import main
import theme
import tweaks


def forbidden(*args, **kwargs):
    raise AssertionError("the UI test must never change the system")


class UiSmoke(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="simpletool-ui-test-")
        self.settings = {"lang": "en", "theme": "navy"}
        self.patches = [
            mock.patch.object(engine, "data_dir", lambda: self.tmp),
            mock.patch.object(engine, "apply", forbidden),
            mock.patch.object(engine, "revert", forbidden),
            mock.patch.object(engine, "restore_snapshot", forbidden),
            mock.patch.object(engine, "create_restore_point", forbidden),
            mock.patch.object(main, "relaunch_as_admin", forbidden),
            mock.patch.object(main, "load_settings", lambda: dict(self.settings)),
            mock.patch.object(main, "save_settings", lambda s: self.settings.update(s)),
        ]
        for patch in self.patches:
            patch.start()

    def tearDown(self):
        for patch in reversed(self.patches):
            patch.stop()
        theme.use("navy")
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
            # колонка: правые края кнопок шапки, первой карточки и кнопки «Применить» совпадают
            app.show_page("privacy", animate=False)
            self.pump(root, 0.3)
            x0 = root.winfo_rootx()
            card = next(iter(app.cards.values()))["card"]
            edges = {app.controls.winfo_rootx() + app.controls.winfo_width() - x0,
                     card.winfo_rootx() + card.winfo_width() - x0,
                     app.apply_button.winfo_rootx() + app.apply_button.winfo_width() - x0}
            self.assertLessEqual(max(edges) - min(edges), 1, f"right edges differ: {edges}")
            # выбор твика включает кнопки, но нажатий нет: растяжка не даст ничего применить
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


if __name__ == "__main__":
    unittest.main()
