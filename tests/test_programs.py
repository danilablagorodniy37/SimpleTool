"""Finding installed programs: shortcut parsing, choosing the process name and building the list (read-only)."""
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import threading
import types
import unittest
import winreg
from unittest import mock

import engine
import programs


def parse(test, data):
    """shortcut_target in a thread with a time limit: a damaged file must not hang the program list."""
    result = []

    def run():
        try:
            result.append((programs.shortcut_target(data), None))
        except Exception as error:  # raised again in the test's thread
            result.append((None, error))

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    thread.join(5)
    test.assertFalse(thread.is_alive(), "parsing the shortcut hangs")
    value, error = result[0]
    if error:
        raise error
    return value


def unicode_lnk(path):
    """A minimal .lnk (MS-SHLLINK): a header with HasLinkInfo | IsUnicode and a LinkInfo with a Unicode local path."""
    text = path.encode("utf-16-le") + b"\0\0"
    # LinkInfoSize, LinkInfoHeaderSize, flags (VolumeIDAndLocalBasePath), four offsets, LocalBasePathOffsetUnicode
    info = struct.pack("<9I", 0x24 + len(text), 0x24, 1, 0, 0, 0, 0, 0x24, 0) + text
    return struct.pack("<I16sI", 0x4C, bytes(16), 0x2 | 0x80).ljust(0x4C, b"\0") + info


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

    def test_cut_off_real_shortcut_fails_cleanly(self):
        """Every truncated copy of a real shortcut either parses or raises what _shortcuts() skips."""
        path = os.path.join(self.dir, "test shortcut.lnk")
        self.make(sys.executable, "--flag")
        with open(path, "rb") as f:
            data = f.read()
        for cut in range(len(data)):
            try:
                parse(self, data[:cut])
            except (struct.error, ValueError, UnicodeDecodeError):
                pass


class DamagedShortcuts(unittest.TestCase):
    def test_unicode_path(self):
        path = "C:\\A\u0100\\app.exe"  # \u0100 is the bytes 00 01: a zero pair at an odd offset is not the end
        self.assertEqual(parse(self, unicode_lnk(path)), (path, None))

    def test_truncated_path_does_not_hang(self):
        data = unicode_lnk(r"C:\Program Files\App\app.exe")
        for cut in (0x4C + 0x24, 0x4C + 0x24 + 6, len(data) - 2, len(data) - 1):  # the path or its end is cut off
            self.assertEqual(parse(self, data[:cut]), (None, None), cut)


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


class FakeKey:
    """A registry key in memory. removed: subkeys counted by QueryInfoKey but gone when EnumKey reaches them."""

    def __init__(self, values=None, subkeys=None, removed=0):
        self.values, self.subkeys, self.removed = values or {}, subkeys or {}, removed

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def fake_winreg(roots):
    """A stand-in for the winreg module over {(hive, path): FakeKey}."""

    def open_key(parent, name):
        key = parent.subkeys.get(name) if isinstance(parent, FakeKey) else roots.get((parent, name))
        if key is None:
            raise FileNotFoundError(name)
        return key

    def enum_key(key, index):
        names = list(key.subkeys)
        if index >= len(names):
            raise OSError(259, "No more data is available")
        return names[index]

    def query_value(key, name):
        if name not in key.values:
            raise FileNotFoundError(name)
        return key.values[name], 1

    return types.SimpleNamespace(OpenKey=open_key, EnumKey=enum_key, QueryValueEx=query_value,
                                 QueryInfoKey=lambda key: (len(key.subkeys) + key.removed, len(key.values), 0),
                                 HKEY_LOCAL_MACHINE=winreg.HKEY_LOCAL_MACHINE,
                                 HKEY_CURRENT_USER=winreg.HKEY_CURRENT_USER)


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

    def test_damaged_registry_entries_skip_only_themselves(self):
        uninstall = FakeKey(subkeys={
            "dword": FakeKey({"DisplayName": 5, "DisplayIcon": r"C:\A\a.exe"}),          # REG_DWORD name
            "multi": FakeKey({"DisplayName": ["A", "B"], "DisplayIcon": r"C:\B\b.exe"}),  # REG_MULTI_SZ name
            "blank": FakeKey({"DisplayName": "  ", "DisplayIcon": r"C:\C\c.exe"}),
            "good": FakeKey({"DisplayName": " Good App ", "DisplayIcon": r'"C:\G\good.exe",0'}),
        }, removed=2)  # two programs were uninstalled while the list was read
        packages = FakeKey(subkeys={"SpotifyAB.SpotifyMusic_1.2_x64__zpdnekdrzrea0": FakeKey()}, removed=1)
        registry = fake_winreg({programs.UNINSTALL[0]: uninstall,
                                (winreg.HKEY_CURRENT_USER, programs.PACKAGES): packages})
        with mock.patch.object(programs, "winreg", registry), \
                mock.patch.object(programs, "_shortcuts", lambda: iter([])):
            found = programs.installed(exists=lambda path: True)
        self.assertEqual(found, [("good", "Good App"), ("spotify", "Spotify")])

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
