"""Finding installed programs: shortcut parsing, choosing the process name and building the list (read-only)."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import engine
import programs


@unittest.skipUnless(sys.platform == "win32", "Windows shortcuts")
class Shortcuts(unittest.TestCase):
    """Windows itself (WScript.Shell) creates the shortcut in the test's temporary folder."""

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="simpletool-lnk-")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def make(self, target, args=""):
        path = os.path.join(self.dir, "test shortcut.lnk")
        script = (f"$s = (New-Object -ComObject WScript.Shell).CreateShortcut('{path}'); "
                  f"$s.TargetPath = '{target}'; $s.Arguments = '{args}'; $s.Save()")
        subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script], check=True,
                       capture_output=True, env=engine.clean_env(), creationflags=subprocess.CREATE_NO_WINDOW)
        with open(path, "rb") as f:
            return programs.shortcut_target(f.read())

    def test_reads_target_and_arguments(self):
        target = sys.executable
        self.assertEqual(self.make(target), (target, None))
        self.assertEqual(self.make(target, "--processStart App.exe"), (target, "--processStart App.exe"))

    def test_garbage_is_not_a_shortcut(self):
        self.assertEqual(programs.shortcut_target(b"not a shortcut"), (None, None))
        self.assertEqual(programs.shortcut_target(b""), (None, None))


class ProcessNames(unittest.TestCase):
    def test_program_paths(self):
        self.assertEqual(programs.process_for(r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe"),
                         "brave")
        self.assertEqual(programs.process_for(r"C:\Program Files\Ollama\ollama app.exe"), "ollama app")

    def test_squirrel_and_aliases(self):
        self.assertEqual(programs.process_for(r"C:\Apps\Discord\Update.exe",
                                              "--processStart Discord.exe"), "discord")
        self.assertEqual(programs.process_for(r"C:\Program Files (x86)\Steam\steam.exe"), "steamwebhelper")

    def test_not_programs(self):
        windows = os.environ.get("SystemRoot", r"C:\Windows")
        for path in (r"C:\Program Files\App\unins000.exe", r"C:\Program Files\App\Uninstall.exe",
                     r"C:\Program Files\App\setup.exe", r"C:\Program Files\App\AppUpdater.exe",
                     r"C:\ProgramData\Package Cache\{0e3bb569}\VC_redist.x64.exe",
                     os.path.join(windows, "System32", "cmd.exe"), r"C:\Program Files\App\readme.htm",
                     r"C:\Python312\python.exe", r"C:\Tools\explorer.exe", None):
            self.assertIsNone(programs.process_for(path), path)
        # A shortcut with arguments is a special mode of the program (for example "App Recovery"), not the program
        self.assertIsNone(programs.process_for(r"C:\Program Files\EA\EALauncher.exe", "-recovery"))


class InstalledList(unittest.TestCase):
    def test_merges_sources_and_skips_missing_files(self):
        shortcuts = [("Brave", r"C:\B\brave.exe", None), ("Uninstall Brave", r"C:\B\unins000.exe", None),
                     ("Cent Browser", r"C:\Cent\chrome.exe", None), ("Gone", r"C:\Gone\gone.exe", None),
                     ("Discord", r"C:\D\Update.exe", "--processStart Discord.exe")]
        entries = [("Brave Browser", r"C:\B\brave.exe", None), ("Telegram Desktop", r"C:\T\Telegram.exe", None)]
        with mock.patch.object(programs, "_shortcuts", lambda: iter(shortcuts)), \
                mock.patch.object(programs, "_uninstall_entries", lambda: iter(entries)), \
                mock.patch.object(programs, "_store_apps", lambda: iter([("ms-teams", "Microsoft Teams")])):
            found = programs.installed(exists=lambda path: "Gone" not in path)
        self.assertEqual(found, [("brave", "Brave"), ("chrome", "Cent Browser"), ("discord", "Discord"),
                                 ("ms-teams", "Microsoft Teams"), ("telegram", "Telegram Desktop")])

    @unittest.skipUnless(sys.platform == "win32", "Windows")
    def test_real_system_scan_is_read_only_and_clean(self):
        found = programs.installed()
        names = [name for name, _ in found]
        self.assertEqual(len(names), len(set(names)))
        for name, title in found:
            self.assertTrue(name and title)
            self.assertFalse(programs.limiter.is_protected(name), name)


if __name__ == "__main__":
    unittest.main()
