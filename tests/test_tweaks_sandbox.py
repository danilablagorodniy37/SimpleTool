"""Every tweak in the catalog inside the sandbox: apply, status, revert, apply again, snapshots.

After a revert or a snapshot restore the registry, tasks and shortcuts must match the original byte for byte,
and values the user set themselves must stay untouched.
"""
import unittest
import winreg

import engine
import tweaks
from engine import OwnedKey, Service, Task, Value
from tests.sandbox import Sandbox, SandboxEscape


def seed(sandbox, user_values):
    """The original "system" state: services on, tasks on, some values set by the user."""
    for tweak in tweaks.TWEAKS:
        for i, op in enumerate(tweak.ops):
            if isinstance(op, Service):
                sandbox.seed_value(op.path, "Start", op.default_start, winreg.REG_DWORD)
            elif isinstance(op, Task):
                sandbox.tasks[op.path.lower()] = False
            elif user_values and isinstance(op, Value) and i % 2 == 0:
                data = 7 if op.kind == winreg.REG_DWORD else "user value"
                sandbox.seed_value(op.path, op.name, data, op.kind)
            elif user_values and isinstance(op, OwnedKey) and i % 3 == 0:
                sandbox.seed_value(op.path, "UserNote", "keep me", winreg.REG_SZ)


class EveryTweak(unittest.TestCase):
    def setUp(self):
        self.sandbox = Sandbox().start()
        # Photo Viewer is not everywhere (for example in CI): check its logic regardless of the PC
        self.requires = {t.id: t.requires for t in tweaks.TWEAKS}
        for tweak in tweaks.TWEAKS:
            tweak.requires = None

    def tearDown(self):
        for tweak in tweaks.TWEAKS:
            tweak.requires = self.requires[tweak.id]
        self.sandbox.stop()

    def check_round_trip(self, user_values):
        seed(self.sandbox, user_values)
        ctx = self.sandbox.ctx
        before = self.sandbox.state()
        for tweak in tweaks.TWEAKS:
            with self.subTest(tweak=tweak.id, user_values=user_values):
                self.assertNotEqual(engine.status(tweak, ctx), "unavailable")
                self.assertEqual(engine.apply(tweak, "ru", ctx), [])
                self.assertEqual(engine.status(tweak, ctx), "applied")
                self.assertEqual(engine.revert(tweak, ctx), [])
                self.assertEqual(self.sandbox.state(), before, "revert must restore the exact original state")
                self.assertNotIn(tweak.id, engine.load_backup())

    def test_apply_then_revert_restores_clean_system(self):
        self.check_round_trip(user_values=False)

    def test_apply_then_revert_keeps_user_values(self):
        self.check_round_trip(user_values=True)

    def test_double_apply_keeps_first_backup(self):
        seed(self.sandbox, user_values=True)
        ctx = self.sandbox.ctx
        before = self.sandbox.state()
        for tweak in tweaks.TWEAKS:
            for lang in ("en", "uk"):  # applying again in another language changes only the menu labels
                self.assertEqual(engine.apply(tweak, lang, ctx), [])
        for tweak in tweaks.TWEAKS:
            self.assertEqual(engine.revert(tweak, ctx), [])
        self.assertEqual(self.sandbox.state(), before)

    def test_snapshot_restores_everything_at_once(self):
        seed(self.sandbox, user_values=True)
        ctx = self.sandbox.ctx
        before = self.sandbox.state()
        engine.take_snapshot(tweaks.TWEAKS, ctx, "initial", {}, "test")
        for tweak in tweaks.TWEAKS:
            engine.apply(tweak, "en", ctx)
        self.assertNotEqual(self.sandbox.state(), before)
        data = engine.list_snapshots()[0][1]
        self.assertEqual(engine.restore_snapshot(tweaks.TWEAKS, data, ctx), [])
        self.assertEqual(self.sandbox.state(), before)

    def test_revert_without_backup_reaches_defaults(self):
        """Tweaks applied by something other than SimpleTool (another program, say): revert sets the defaults."""
        seed(self.sandbox, user_values=False)
        ctx = self.sandbox.ctx
        for tweak in tweaks.TWEAKS:
            engine.apply(tweak, "en", ctx)
        engine.save_backup({})  # as if there were no backup
        for tweak in tweaks.TWEAKS:
            with self.subTest(tweak=tweak.id):
                self.assertEqual(engine.revert(tweak, ctx), [])
                self.assertIn(engine.status(tweak, ctx), ("not_applied", "partial"))
        # Services start again, tasks are enabled again
        for tweak in tweaks.TWEAKS:
            for op in tweak.ops:
                if isinstance(op, Service):
                    self.assertEqual(engine.read_value(op.path, "Start")[0], op.default_start)
                if isinstance(op, Task):
                    self.assertFalse(self.sandbox.tasks[op.path.lower()])

    def test_only_allowed_commands_were_run(self):
        seed(self.sandbox, user_values=False)
        for tweak in tweaks.TWEAKS:
            engine.apply(tweak, "en", self.sandbox.ctx)
            engine.revert(tweak, self.sandbox.ctx)
        programs = {cmd[0] for cmd in self.sandbox.commands}
        self.assertLessEqual(programs, {"sc.exe", "schtasks.exe"})
        stopped = {cmd[2] for cmd in self.sandbox.commands if cmd[0] == "sc.exe"}
        self.assertLessEqual(stopped, {"DiagTrack", "dmwappushservice", "NvTelemetryContainer"})


class SandboxTripwire(unittest.TestCase):
    """The tripwire itself must fire, otherwise the other tests guarantee nothing."""

    def test_write_outside_sandbox_is_blocked(self):
        with Sandbox() as sandbox:
            with self.assertRaises(SandboxEscape):
                engine.winreg.CreateKeyEx(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Test", 0, winreg.KEY_WRITE)
            with self.assertRaises(SandboxEscape):
                engine.winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft", 0, winreg.KEY_READ)
            with self.assertRaises(SandboxEscape):
                engine.run(["reg.exe", "delete", r"HKLM\SOFTWARE\Test", "/f"])
            with self.assertRaises(SandboxEscape):
                engine.powershell("Stop-Computer")
            self.assertTrue(sandbox.subkey(r"HKLM\SOFTWARE\X").startswith(sandbox.root))

    def test_sandbox_is_removed_afterwards(self):
        with Sandbox() as sandbox:
            sandbox.seed_value(r"HKCU\Software\Probe", "x", 1, winreg.REG_DWORD)
            root = sandbox.root
        with self.assertRaises(FileNotFoundError):
            winreg.OpenKey(winreg.HKEY_CURRENT_USER, root)


if __name__ == "__main__":
    unittest.main()
