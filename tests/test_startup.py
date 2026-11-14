"""Startup page logic: reading the entries, turning them on and off as Task Manager does, removing dead ones.

The registry is replaced by a dictionary: nothing on the PC is read or changed.
"""
import json
import os
import shutil
import struct
import tempfile
import unittest
import winreg
from unittest import mock

import engine
import startup

RUN_USER = r"HKCU\Software\Microsoft\Windows\CurrentVersion\Run"
RUN_ALL = r"HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Run"
APPROVED_USER = rf"HKCU\{startup.APPROVED}\Run"
APPROVED_ALL = rf"HKLM\{startup.APPROVED}\Run"
SYSTEM32 = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32")


class FakeRegistry:
    def __init__(self, values=None, keys=None):
        self.values = values or {}   # key path -> {name: data}
        self.keys = keys or {}       # key path -> [subkey names]
        self.written, self.deleted = [], []

    def read_values(self, path):
        return list(self.values.get(path, {}).items())

    def subkeys(self, path):
        return list(self.keys.get(path, []))

    def read(self, path, name):
        return self.values.get(path, {}).get(name)

    def write(self, path, name, data, kind):
        self.written.append((path, name, data, kind))
        self.values.setdefault(path, {})[name] = data

    def delete(self, path, name):
        self.deleted.append((path, name))
        self.values.get(path, {}).pop(name, None)


class StartupTest(unittest.TestCase):
    def setUp(self):
        self.registry = FakeRegistry()
        self.tmp = tempfile.mkdtemp(prefix="simpletool-startup-test-")
        self.patches = [
            mock.patch.object(startup, "_values", self.registry.read_values),
            mock.patch.object(startup, "_subkeys", self.registry.subkeys),
            mock.patch.object(startup, "_read", self.registry.read),
            mock.patch.object(engine, "write_value", self.registry.write),
            mock.patch.object(engine, "delete_value", self.registry.delete),
            mock.patch.object(engine, "read_value", lambda path, name: (self.registry.read(path, name), winreg.REG_SZ)
                              if self.registry.read(path, name) is not None else None),
            mock.patch.object(engine, "data_dir", lambda: self.tmp),
            mock.patch.object(startup, "FOLDERS", []),
        ]
        for patch in self.patches:
            patch.start()

    def tearDown(self):
        for patch in reversed(self.patches):
            patch.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_approved_data(self):
        self.assertTrue(startup.approved_on(None), "no mark: on")
        self.assertTrue(startup.approved_on(startup.APPROVED_ON))
        self.assertTrue(startup.approved_on(bytes.fromhex("060000000000000000000000")))
        self.assertFalse(startup.approved_on(bytes.fromhex("03000000c0142a70fb0ddb01")))
        self.assertFalse(startup.approved_on(bytes.fromhex("07000000b09034de97b9dc01")))

    def test_program_file(self):
        notepad = os.path.join(SYSTEM32, "notepad.exe")
        self.assertEqual(startup.program_file(f'"{notepad}" --hidden'), notepad)
        self.assertEqual(startup.program_file(r"C:\Program Files\Docker\Docker\Docker Desktop.exe -Autostart"),
                         r"C:\Program Files\Docker\Docker\Docker Desktop.exe")
        self.assertEqual(os.path.normcase(startup.program_file(r"%windir%\system32\notepad.exe")),
                         os.path.normcase(notepad))
        self.assertEqual(os.path.normcase(startup.program_file("notepad.exe")), os.path.normcase(notepad),
                         "found on the PATH")
        self.assertEqual(startup.program_file(r'rundll32.exe "C:\Tools\helper.dll",Start'), r"C:\Tools\helper.dll",
                         "the DLL rundll32 runs")
        self.assertEqual(startup.program_file(r"C:\WINDOWS\system32\rundll32.exe C:\Tools\x.dll,Run"),
                         r"C:\Tools\x.dll")

    def test_run_entries_and_their_marks(self):
        notepad = os.path.join(SYSTEM32, "notepad.exe")
        self.registry.values = {
            RUN_USER: {"Tool": f'"{notepad}" /background', "Gone": r'"C:\nowhere-at-all\gone.exe"', "": "x"},
            APPROVED_USER: {"gone": bytes.fromhex("03000000c0142a70fb0ddb01")},
            RUN_ALL: {"Tray": notepad},
            APPROVED_ALL: {"Tray": startup.APPROVED_ON, "Removed long ago": bytes.fromhex("030000000000000000000000")},
        }
        entries = {e.name: e for e in startup.entries(impact=[{"name": "Notepad", "path": notepad, "cpu": 1500,
                                                               "disk": 10, "starts": 3}])}
        self.assertEqual(sorted(entries), ["Gone", "Tool", "Tray"], "no empty names, no marks without entries")
        tool, gone, tray = entries["Tool"], entries["Gone"], entries["Tray"]
        self.assertTrue(tool.enabled and tray.enabled)
        self.assertFalse(gone.enabled, "marks are matched case aside")
        self.assertEqual((tool.scope, tray.scope), ("HKCU", "HKLM"))
        self.assertTrue(tray.needs_admin and not tool.needs_admin)
        self.assertEqual(tool.approved, (APPROVED_USER, "Tool"))
        self.assertEqual(tool.impact, {"cpu": 1500, "disk": 10, "starts": 3})
        self.assertTrue(gone.missing and not tool.missing)
        self.assertNotEqual(tool.title, "Tool", "the description of the program's file")

    def test_updater_title_is_not_the_program(self):
        """Discord starts through Squirrel's Update.exe ("Update" by GitHub): the entry's own name is shown."""
        update = os.path.join(SYSTEM32, "notepad.exe")
        self.registry.values = {RUN_USER: {"Discord": f'"{update}" --processStart Discord.exe'}}
        with mock.patch("diagnostics.file_description", lambda path: "Update"), \
                mock.patch("diagnostics.version_string", lambda path, field: "GitHub"):
            entry = startup.entries(impact=[])[0]
        self.assertEqual((entry.title, entry.publisher), ("Discord", ""))

    def test_turning_off_and_on(self):
        self.registry.values = {RUN_USER: {"Tool": r"C:\Tools\tool.exe"}}
        entry = startup.entries(impact=[])[0]
        startup.set_enabled(entry, False)
        path, name, data, kind = self.registry.written[-1]
        self.assertEqual((path, name, kind), (APPROVED_USER, "Tool", winreg.REG_BINARY))
        self.assertEqual(len(data), 12)
        self.assertEqual(data[:4], b"\x03\0\0\0")
        self.assertGreater(struct.unpack("<Q", data[4:])[0], 133_000_000_000_000_000, "the time it was turned off")
        self.assertFalse(entry.enabled)
        self.assertEqual(self.registry.values[RUN_USER], {"Tool": r"C:\Tools\tool.exe"}, "the entry is untouched")
        startup.set_enabled(entry, True)
        self.assertEqual(self.registry.written[-1][2], startup.APPROVED_ON)
        self.assertTrue(entry.enabled)

    def test_store_app_tasks(self):
        tasks, packages = startup.APP_TASKS, startup.APP_PACKAGES
        full = "AppleInc.iTunes_12139.12003.62022.0_x64__nzyj5cx40ttqa"
        family = "AppleInc.iTunes_nzyj5cx40ttqa"
        self.registry.keys = {tasks: [family, "Policy.App_x"],
                              rf"{tasks}\{family}": ["Schemas", "HAM", "Helper", "Device"],
                              rf"{tasks}\Policy.App_x": ["Schemas", "Task"]}
        self.registry.values = {
            rf"{tasks}\{family}\Schemas": {"PackageFullName": full},
            rf"{tasks}\{family}\Helper": {"State": 2},
            rf"{tasks}\{family}\Device": {"State": 1},
            rf"{tasks}\Policy.App_x\Schemas": {"PackageFullName": "Policy.App_1.0.0.0_x64__x"},
            rf"{tasks}\Policy.App_x\Task": {"State": 4},
            rf"{packages}\{full}": {"DisplayName": "iTunes"},
        }
        entries = {e.name: e for e in startup.entries(impact=[])}
        self.assertEqual(sorted(entries), ["App", "iTunes (Device)", "iTunes (Helper)"],
                         "HAM is not a startup task; two tasks of one app are told apart")
        helper, policy = entries["iTunes (Helper)"], entries["App"]
        self.assertTrue(helper.enabled and helper.source == "app" and not helper.missing)
        self.assertFalse(entries["iTunes (Device)"].enabled)
        self.assertTrue(policy.enabled and policy.policy and not policy.changeable)
        startup.set_enabled(helper, False)
        self.assertIn((rf"{tasks}\{family}\Helper", "State", startup.TASK_DISABLED_BY_USER, winreg.REG_DWORD),
                      self.registry.written)
        startup.set_enabled(helper, True)
        self.assertEqual(self.registry.values[rf"{tasks}\{family}\Helper"]["State"], startup.TASK_ENABLED)
        with self.assertRaises(PermissionError):
            startup.set_enabled(policy, False)

    def test_resource_names(self):
        full = "Microsoft.Windows.Photos_2026.1.0.0_x64__8wekyb3d8bbwe"
        name = "Microsoft.Windows.Photos"
        self.assertEqual(startup.resource_candidates("ms-resource:AppName", full),
                         [f"@{{{full}?ms-resource://{name}/Resources/AppName}}",
                          f"@{{{full}?ms-resource://{name}/AppName}}"])
        self.assertEqual(startup.resource_candidates("ms-resource:/Resources/Title", full),
                         [f"@{{{full}?ms-resource://{name}/Resources/Title}}"])
        uri = "ms-resource://MicrosoftWindows.CrossDevice/CrossDevice.Core/Resources/AppName"
        self.assertEqual(startup.resource_candidates(uri, full), [f"@{{{full}?{uri}}}"])
        self.assertEqual(startup.resource_candidates("Plain name", full), ["Plain name"])

    def test_removing_only_dead_entries(self):
        self.registry.values = {RUN_USER: {"Gone": r'"C:\nowhere-at-all\gone.exe" -min',
                                           "Tool": os.path.join(SYSTEM32, "notepad.exe")},
                                APPROVED_USER: {"Gone": startup.APPROVED_ON}}
        entries = {e.name: e for e in startup.entries(impact=[])}
        with self.assertRaises(ValueError):
            startup.remove(entries["Tool"])
        startup.remove(entries["Gone"])
        self.assertNotIn("Gone", self.registry.values[RUN_USER])
        self.assertNotIn("Gone", self.registry.values[APPROVED_USER], "its on/off mark goes too")
        with open(startup.removed_file(), encoding="utf-8") as f:
            saved = json.load(f)
        self.assertEqual([(s["key"], s["name"], s["data"]) for s in saved],
                         [(RUN_USER, "Gone", r'"C:\nowhere-at-all\gone.exe" -min')], "saved before it is deleted")

    def test_startup_folder_shortcuts(self):
        folder = os.path.join(self.tmp, "Startup")
        os.makedirs(folder)
        for name in ("desktop.ini", "Tool.lnk", "Off.lnk"):
            open(os.path.join(folder, name), "wb").close()
        approval = rf"HKCU\{startup.APPROVED}\StartupFolder"
        self.registry.values = {approval: {"off.lnk": bytes.fromhex("03000000c0142a70fb0ddb01")}}
        targets = {"Tool.lnk": r"C:\nowhere-at-all\tool.exe", "Off.lnk": ""}
        with mock.patch.object(startup, "FOLDERS", [("HKCU", folder, approval)]), \
                mock.patch("uninstaller._shortcut_target", lambda path: targets[os.path.basename(path)]), \
                mock.patch("uninstaller.to_recycle_bin") as recycle:
            entries = {e.name: e for e in startup.entries(impact=[])}
            self.assertEqual(sorted(entries), ["Off", "Tool"])
            self.assertFalse(entries["Off"].enabled)
            self.assertEqual(entries["Tool"].approved, (approval, "Tool.lnk"))
            self.assertTrue(entries["Tool"].missing)
            startup.remove(entries["Tool"])
            recycle.assert_called_once_with(os.path.join(folder, "Tool.lnk"))


if __name__ == "__main__":
    unittest.main()
