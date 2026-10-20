"""Движок в отдельных ситуациях: статусы, сбои посреди применения, границы удаления, снимки, разбор вывода."""
import os
import subprocess
import unittest
import winreg
from unittest import mock

import engine
from engine import ABSENT, OwnedKey, Task, Tweak, Unknown, Value
from tests.sandbox import Sandbox

ROOT = r"HKCU\Software\Probe"


class BrokenValue(Value):
    """Значение, запись которого падает, как при нехватке прав."""

    def apply(self, lang):
        raise PermissionError(5, "Access is denied")


class UnreadableValue(Value):
    def snapshot(self, ctx):
        raise PermissionError(5, "Access is denied")

    def applied(self, ctx):
        raise PermissionError(5, "Access is denied")


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.sandbox = Sandbox().start()
        self.ctx = self.sandbox.ctx

    def tearDown(self):
        self.sandbox.stop()

    def test_status_matrix(self):
        on, off = Value(ROOT, "On", 1), Value(ROOT, "Off", 1)
        self.sandbox.seed_value(ROOT, "On", 1, winreg.REG_DWORD)
        self.assertEqual(engine.status(Tweak("a", "system", [on]), self.ctx), "applied")
        self.assertEqual(engine.status(Tweak("b", "system", [off]), self.ctx), "not_applied")
        self.assertEqual(engine.status(Tweak("c", "system", [on, off]), self.ctx), "partial")
        self.assertEqual(engine.status(Tweak("d", "system", [Task("Missing\\Task")]), self.ctx), "unavailable")
        self.assertEqual(engine.status(Tweak("e", "system", [on], requires=lambda: False), self.ctx), "unavailable")
        self.assertEqual(engine.status(Tweak("f", "system", [UnreadableValue(ROOT, "X", 1)]), self.ctx), "unknown")
        # Неизвестная часть при точно не применённой другой — «не применено», а не «неизвестно»
        self.assertEqual(engine.status(Tweak("g", "system", [off, UnreadableValue(ROOT, "X", 1)]), self.ctx),
                         "not_applied")

    def test_tasks_unknown_when_scheduler_unreadable(self):
        class NoTasks:
            tasks = None
        status, rows = engine.check(Tweak("t", "privacy", [Task("Microsoft\\Windows\\X")]), NoTasks())
        self.assertEqual(status, "unknown")
        self.assertEqual(rows[0][2], "tasks_unavailable")
        with self.assertRaises(Unknown):
            Task("A").applied(NoTasks())

    def test_failed_operation_does_not_stop_others(self):
        tweak = Tweak("x", "system", [Value(ROOT, "First", 1), BrokenValue(ROOT, "Broken", 1), Value(ROOT, "Last", 1)])
        errors = engine.apply(tweak, "en", self.ctx)
        self.assertEqual(len(errors), 1)
        self.assertIn("Access is denied", errors[0])
        self.assertEqual(engine.read_value(ROOT, "First")[0], 1)
        self.assertEqual(engine.read_value(ROOT, "Last")[0], 1)
        self.assertIn("x", engine.load_backup())  # откат возможен и после частичного сбоя
        self.assertEqual(engine.revert(tweak, self.ctx), [])
        self.assertIsNone(engine.read_value(ROOT, "First"))

    def test_value_without_snapshot_is_not_applied(self):
        """Если исходное значение не прочитать, менять его нельзя: потом его не вернуть."""
        tweak = Tweak("y", "system", [UnreadableValue(ROOT, "Secret", 1), Value(ROOT, "Other", 1)])
        errors = engine.apply(tweak, "en", self.ctx)
        self.assertEqual(len(errors), 1)
        self.assertIsNone(engine.read_value(ROOT, "Secret"))
        self.assertEqual(engine.read_value(ROOT, "Other")[0], 1)

    def test_revert_keeps_backup_when_it_fails(self):
        tweak = Tweak("z", "system", [Value(ROOT, "A", 1)])
        engine.apply(tweak, "en", self.ctx)
        with mock.patch.object(Value, "restore", side_effect=PermissionError(5, "denied")):
            self.assertTrue(engine.revert(tweak, self.ctx))
        self.assertIn("z", engine.load_backup())

    def test_existing_value_and_type_come_back(self):
        self.sandbox.seed_value(ROOT, "Text", "original", winreg.REG_EXPAND_SZ)
        self.sandbox.seed_value(ROOT, "Blob", b"\x00\x01\xff", winreg.REG_BINARY)
        tweak = Tweak("t", "system", [Value(ROOT, "Text", "new", winreg.REG_SZ), Value(ROOT, "Blob", 5)])
        engine.apply(tweak, "en", self.ctx)
        engine.revert(tweak, self.ctx)
        self.assertEqual(engine.read_value(ROOT, "Text"), ("original", winreg.REG_EXPAND_SZ))
        self.assertEqual(engine.read_value(ROOT, "Blob"), (b"\x00\x01\xff", winreg.REG_BINARY))

    def test_pruning_never_goes_above_classes_or_deletes_filled_keys(self):
        classes = r"HKCU\Software\Classes"
        self.sandbox.seed_value(classes + r"\exefile", "Keep", "user data", winreg.REG_SZ)
        key = OwnedKey(classes + r"\exefile\shell\SimpleTool.Test")
        key.apply("en")
        key.reset()
        self.assertTrue(engine.key_exists(classes + r"\exefile"), "a key with user data must stay")
        self.assertFalse(engine.key_exists(classes + r"\exefile\shell"), "the empty key SimpleTool created goes")
        lonely = OwnedKey(classes + r"\Nothing\shell\SimpleTool.Test")
        lonely.apply("en")
        lonely.reset()
        self.assertTrue(engine.key_exists(classes), "pruning stops at ...\\Classes")

    def test_pruning_ignores_keys_outside_classes(self):
        self.sandbox.seed_key(r"HKCU\Software\Empty\Parent")
        engine.prune_empty_parents(r"HKCU\Software\Empty\Parent\Child")
        self.assertTrue(engine.key_exists(r"HKCU\Software\Empty\Parent"))

    def test_snapshot_retention(self):
        tweak = Tweak("r", "system", [Value(ROOT, "A", 1)])
        engine.take_snapshot([tweak], self.ctx, "initial", {}, "test")
        engine.take_snapshot([tweak], self.ctx, "manual", {}, "test")
        for _ in range(engine.AUTO_SNAPSHOTS_KEPT + 5):
            engine.take_snapshot([tweak], self.ctx, "before_apply", {}, "test")
        kinds = [data["kind"] for _, data in engine.list_snapshots()]
        self.assertEqual(kinds.count("initial"), 1)
        self.assertEqual(kinds.count("manual"), 1)
        self.assertEqual(kinds.count("before_apply"), engine.AUTO_SNAPSHOTS_KEPT)

    def test_corrupt_files_do_not_break_loading(self):
        with open(os.path.join(engine.snapshots_dir(), "broken.json"), "w") as f:
            f.write("{not json")
        with open(engine.backup_path(), "w") as f:
            f.write("garbage")
        self.assertEqual(engine.list_snapshots(), [])
        self.assertEqual(engine.load_backup(), {})

    def test_task_restore_is_symmetric(self):
        self.sandbox.tasks["a\\b"] = True
        Task("A\\B").restore(True)
        self.assertFalse(self.sandbox.tasks["a\\b"])
        Task("A\\B").restore(False)
        self.assertTrue(self.sandbox.tasks["a\\b"])

    def test_cyrillic_shortcut_names(self):
        names = {"en": "Restart", "ru": "Перезагрузка", "uk": "Перезавантаження"}
        shortcut = engine.Shortcut(names, r"%SystemRoot%\System32\shutdown.exe", "/r /t 0", "")
        tweak = Tweak("s", "system", [shortcut])
        engine.apply(tweak, "uk", self.ctx)
        self.assertTrue(os.path.exists(os.path.join(self.sandbox.tmp, "Перезавантаження.lnk")))
        engine.revert(tweak, self.ctx)
        self.assertEqual(self.sandbox.state()["shortcuts"], [])

    def test_absent_default_deletes_value(self):
        value = Value(ROOT, "Policy", 1)
        self.assertIs(value.default, ABSENT)
        value.apply("en")
        value.reset()
        self.assertIsNone(engine.read_value(ROOT, "Policy"))


class ParsingTests(unittest.TestCase):
    """Разбор вывода PowerShell — без запуска PowerShell."""

    def run_tasks(self, stdout, code=0):
        result = subprocess.CompletedProcess([], code, stdout=stdout, stderr="")
        with mock.patch.object(engine.subprocess, "run", return_value=result):
            return engine.load_tasks()

    def test_load_tasks(self):
        out = "﻿\\Microsoft\\Windows\\Autochk\\Proxy|3\n\\NvTmRep_{X}|1\n\\Задача с именем|1\n"
        tasks = self.run_tasks(out)
        self.assertEqual(tasks, {"microsoft\\windows\\autochk\\proxy": False, "nvtmrep_{x}": True,
                                 "задача с именем": True})

    def test_load_tasks_failure(self):
        self.assertIsNone(self.run_tasks("", code=1))
        with mock.patch.object(engine.subprocess, "run", side_effect=OSError("powershell missing")):
            self.assertIsNone(engine.load_tasks())

    def test_restore_point_results(self):
        with mock.patch.object(engine, "powershell", return_value="CREATED\r\n"):
            self.assertEqual(engine.create_restore_point(), (True, ""))
        with mock.patch.object(engine, "powershell", return_value="NOT CREATED: A new restore point cannot be created"):
            self.assertEqual(engine.create_restore_point(), (False, "A new restore point cannot be created"))
        with mock.patch.object(engine, "powershell", side_effect=RuntimeError("System Restore is disabled")):
            self.assertEqual(engine.create_restore_point(), (False, "System Restore is disabled"))


if __name__ == "__main__":
    unittest.main()
