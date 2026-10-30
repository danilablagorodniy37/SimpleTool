"""Programs: names, what is never offered, the leftover search on a made-up profile, removing leftovers with backups,
icons, and waiting for an uninstaller and the programs it starts."""
import datetime
import json
import os
import shutil
import struct
import tempfile
import time
import unittest
import zlib
from unittest import mock

import raster
import uninstaller
from uninstaller import Program

PROFILE = r"C:\Users\A"  # a made-up user profile for the tests, secret-scan: allow


class Names(unittest.TestCase):
    def test_names_without_versions(self):
        self.assertEqual(uninstaller.compact("7-Zip 24.09 (x64)"), "7zip")
        self.assertEqual(uninstaller.compact("Notepad++ (64-bit x64)"), "notepad++")
        self.assertEqual(uninstaller.compact("Python 3.12.9 (64-bit)"), "python")
        self.assertEqual(uninstaller.compact("GIMP 2.10.38-1"), "gimp")
        self.assertEqual(uninstaller.compact("Proton Mail Bridge 3.27.0"), "protonmailbridge")
        self.assertEqual(uninstaller.compact("proton_mail"), "protonmail")

    def test_a_name_another_program_shares_is_not_used(self):
        python312, python311 = Program("k1", "Python 3.12.9 (64-bit)"), Program("k2", "Python 3.11.9 (64-bit)")
        self.assertEqual(uninstaller.program_names(python312, [python311]), set(), "every Python is 'python'")
        mail = Program("k3", "Proton Mail", location=rf"{PROFILE}\AppData\Local\proton_mail")
        bridge = Program("k4", "Proton Mail Bridge")
        self.assertEqual(uninstaller.program_names(mail, [bridge]), set(), "'protonmail' also begins the Bridge")
        self.assertEqual(uninstaller.program_names(bridge, [mail]), {"protonmailbridge"})
        self.assertEqual(uninstaller.program_names(Program("k5", "Hub")), set(), "too short")
        self.assertEqual(uninstaller.program_names(Program("k6", "Steam")), set(), "Steam's folder holds the games")

    def test_icon_values_and_commands(self):
        self.assertEqual(uninstaller.parse_icon('"C:\\A\\b.exe",0'), ("C:\\A\\b.exe", 0))
        self.assertEqual(uninstaller.parse_icon("C:\\A\\b.ico"), ("C:\\A\\b.ico", 0))
        self.assertEqual(uninstaller.parse_icon("C:\\A\\b.dll,-101"), ("C:\\A\\b.dll", -101))
        self.assertIsNone(uninstaller.parse_icon(""))
        self.assertEqual(uninstaller.command_program('"C:\\P F\\unins000.exe" /SILENT'), "C:\\P F\\unins000.exe")
        self.assertEqual(uninstaller.command_program("C:\\P F\\uninstall.exe /S"), "C:\\P F\\uninstall.exe")


class Entries(unittest.TestCase):
    def test_windows_installer_products_are_removed_not_repaired(self):
        code = "{A1E4E9F3-35D6-4662-952B-17E01C79E35D}"
        program = Program("k", "Office", uninstall=f"MsiExec.exe /I{code}", msi=code)
        command = uninstaller.uninstall_command(program)
        self.assertTrue(command.lower().endswith(f"msiexec.exe\" /x {code.lower()}"), command)

    def test_names_of_folders_in_the_command_are_filled_in(self):
        with mock.patch.dict(os.environ, {"ProgramFiles": r"C:\Program Files"}):
            program = Program("k", "Tool", uninstall=r'"%ProgramFiles%\Tool\unins000.exe" /SILENT')
            self.assertEqual(uninstaller.uninstall_command(program), r'"C:\Program Files\Tool\unins000.exe" /SILENT')

    def test_what_can_be_removed(self):
        self.assertFalse(Program("k", "Edge", removable=False).uninstaller_missing, "Windows keeps it")
        self.assertTrue(Program("k", "Old", uninstall='"C:\\nowhere-at-all\\unins000.exe"').uninstaller_missing)
        self.assertFalse(Program("k", "Tool", uninstall="rundll32.exe tool.dll,Remove").uninstaller_missing,
                         "not a full path: nothing to tell")


class Safety(unittest.TestCase):
    def setUp(self):
        self.env = mock.patch.dict(os.environ, {
            "SystemDrive": "C:", "SystemRoot": r"C:\Windows", "ProgramFiles": r"C:\Program Files",
            "ProgramFiles(x86)": r"C:\Program Files (x86)", "ProgramData": r"C:\ProgramData",
            "USERPROFILE": PROFILE, "APPDATA": rf"{PROFILE}\AppData\Roaming",
            "LOCALAPPDATA": rf"{PROFILE}\AppData\Local", "PUBLIC": r"C:\Users\Public", "TEMP": rf"{PROFILE}\Temp"})
        self.env.start()

    def tearDown(self):
        self.env.stop()

    def test_folders_never_offered(self):
        for folder in ("C:\\", r"C:\Windows", r"C:\Windows\System32\Tool", r"C:\Program Files",
                       rf"{PROFILE}\AppData\Roaming", rf"{PROFILE}\AppData\Local\Programs",
                       r"C:\Program Files\Common Files", rf"{PROFILE}\AppData\Roaming\Microsoft",
                       rf"{PROFILE}\AppData\Roaming\Microsoft\Windows\Start Menu\Programs", PROFILE):
            self.assertTrue(uninstaller.protected_folder(folder), folder)
        self.assertFalse(uninstaller.protected_folder(r"C:\Program Files\Good Tool"))
        # The folder of another installed program, or one that holds it
        self.assertTrue(uninstaller.protected_folder(r"C:\Program Files\Vendor", [r"C:\Program Files\Vendor\Other"]))
        self.assertTrue(uninstaller.protected_folder(r"C:\Apps\Other", [r"C:\Apps\Other"]))

    def test_keys_never_offered(self):
        for key in (r"HKCU\Software", r"HKCU\Software\Microsoft\Tool", r"HKLM\SOFTWARE\WOW6432Node\Google\Chrome",
                    r"HKCU\Software\Classes\Tool", r"HKCU\Software\Policies\Tool", r"HKCU\System\Tool"):
            self.assertTrue(uninstaller.protected_key(key), key)
        for key in (r"HKCU\Software\Discord", r"HKLM\SOFTWARE\WOW6432Node\Notepad++"):
            self.assertFalse(uninstaller.protected_key(key), key)


class Leftovers(unittest.TestCase):
    """A made-up profile in a temporary folder and a made-up registry."""

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="simpletool-uninstall-test-")
        paths = {"ProgramFiles": "Program Files", "ProgramFiles(x86)": "Program Files (x86)",
                 "ProgramData": "ProgramData", "USERPROFILE": "Users\\A", "APPDATA": "Users\\A\\AppData\\Roaming",
                 "LOCALAPPDATA": "Users\\A\\AppData\\Local", "PUBLIC": "Users\\Public", "TEMP": "Users\\A\\Temp"}
        env = {name: os.path.join(self.root, sub) for name, sub in paths.items()}
        env["SystemRoot"] = os.path.join(self.root, "Windows")
        for folder in env.values():
            os.makedirs(folder, exist_ok=True)
        env["SystemDrive"] = self.root[:2]
        self.env = env
        self.patch = mock.patch.dict(os.environ, env)
        self.patch.start()
        self.registry = {}  # key -> [subkey names]
        self.values = {}    # key -> [(name, data)]
        self.patches = [mock.patch.object(uninstaller, "_subkey_names", lambda path: self.registry.get(path, [])),
                        mock.patch.object(uninstaller, "_values", lambda path: self.values.get(path, [])),
                        mock.patch.object(uninstaller, "_key_counts",
                                          lambda path: (len(self.registry.get(path, [])), 0)),
                        mock.patch.object(uninstaller.engine, "key_exists", lambda path: False),
                        mock.patch.object(uninstaller.engine, "read_value", lambda path, name: None)]
        for patch in self.patches:
            patch.start()

    def tearDown(self):
        for patch in reversed(self.patches):
            patch.stop()
        self.patch.stop()
        shutil.rmtree(self.root, ignore_errors=True)

    def folder(self, base, *parts, files=("left.txt",)):
        path = os.path.join(self.env[base], *parts)
        os.makedirs(path, exist_ok=True)
        for name in files:
            with open(os.path.join(path, name), "w") as f:
                f.write("x")
        return path

    def test_what_a_removed_program_left(self):
        install = self.folder("ProgramFiles", "Good Tool")
        data = self.folder("APPDATA", "Good Tool")
        vendor = self.folder("LOCALAPPDATA", "Acme", "Good Tool")
        self.folder("LOCALAPPDATA", "Acme", "Other Tool")  # another product of the publisher stays
        self.folder("APPDATA", "Good Tool Pro")  # another program, whose name begins the same way, stays
        self.registry = {r"HKCU\Software": ["Good Tool", "Acme", "Unrelated"],
                         r"HKCU\Software\Acme": ["Good Tool", "Other Tool"]}
        self.values = {r"HKCU\Software\Microsoft\Windows\CurrentVersion\Run":
                       [("Good Tool", f'"{install}\\goodtool.exe" --tray'), ("Discord", "C:\\x\\Update.exe")]}
        program = Program(r"HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall\GoodTool", "Good Tool 2.1 (x64)",
                          publisher="Acme", location=install)
        found = uninstaller.find_leftovers(program, [Program("other", "Other Tool")])
        self.assertEqual({(f["kind"], f["path"], f["name"]) for f in found}, {
            ("folder", install, ""), ("folder", data, ""), ("folder", vendor, ""),
            ("key", r"HKCU\Software\Good Tool", ""), ("key", r"HKCU\Software\Acme\Good Tool", ""),
            ("value", r"HKCU\Software\Microsoft\Windows\CurrentVersion\Run", "Good Tool")})
        self.assertTrue(all(f["size"] == 1 for f in found if f["kind"] == "folder"), "a byte each")

    def test_a_publisher_key_with_nothing_else_goes_whole(self):
        self.registry = {r"HKLM\SOFTWARE": ["Acme"], r"HKLM\SOFTWARE\Acme": ["Good Tool"]}
        found = uninstaller.find_leftovers(Program("k", "Good Tool", publisher="Acme"))
        self.assertEqual([f["path"] for f in found], [r"HKLM\SOFTWARE\Acme"])

    def test_the_folder_of_a_program_still_installed_is_kept(self):
        install = self.folder("ProgramFiles", "Good Tool")
        other = Program("other", "Good Tool Helper", location=install)  # wrongly shares the folder
        self.assertEqual(uninstaller.find_leftovers(Program("k", "Good Tool", location=install), [other]), [])

    def test_an_entry_naming_a_whole_library_is_not_trusted(self):
        # The entry of a game names the folder of all the user's games as its install folder
        library = self.folder("USERPROFILE", "MyLibrary")
        program = Program("k", "Some Game", location=library)
        self.assertEqual(uninstaller.find_leftovers(program), [], "the folder does not carry the program's name")

    def test_shortcuts_that_lead_nowhere(self):
        install = os.path.join(self.env["ProgramFiles"], "Good Tool")  # already removed by the uninstaller
        menu = self.folder("APPDATA", r"Microsoft\Windows\Start Menu\Programs", files=())
        desktop = self.folder("USERPROFILE", "Desktop", files=())
        dead, alive = os.path.join(menu, "Good Tool.lnk"), os.path.join(desktop, "Good Tool.lnk")
        for path in (dead, alive, os.path.join(desktop, "Other.lnk")):
            open(path, "wb").close()
        targets = {dead: install + r"\goodtool.exe", alive: os.environ["SystemRoot"],
                   os.path.join(desktop, "Other.lnk"): install + r"\other.exe"}
        with mock.patch.object(uninstaller, "_shortcut_target", lambda path: targets[path]):
            found = uninstaller.find_leftovers(Program("k", "Good Tool"))
        self.assertEqual([(f["kind"], f["path"]) for f in found], [("file", dead)],
                         "a shortcut that still works stays, and so does one with another name")


class Location(unittest.TestCase):
    """Where "Open file location" goes: the program's own folder, never Windows' own folders."""

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="simpletool-location-test-")
        self.windows = os.path.join(self.root, "Windows")
        self.patch = mock.patch.dict(os.environ, {"SystemRoot": self.windows})
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        shutil.rmtree(self.root, ignore_errors=True)

    def file(self, *parts):
        path = os.path.join(self.root, *parts)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        open(path, "wb").close()
        return path

    def test_the_install_folder_with_the_program_selected(self):
        exe = self.file("Apps", "Good Tool", "goodtool.exe")
        folder = os.path.dirname(exe)
        self.assertEqual(uninstaller.program_location(Program("k", "Good Tool", location=folder, icon=(exe, 0))),
                         (folder, exe))
        other = self.file("Windows", "System32", "shell32.exe")
        self.assertEqual(uninstaller.program_location(Program("k", "Good Tool", location=folder, icon=(other, 3))),
                         (folder, None), "an icon from elsewhere is not the program")

    def test_without_an_install_folder(self):
        exe = self.file("Apps", "Tool", "tool.exe")
        self.assertEqual(uninstaller.program_location(Program("k", "Tool", icon=(exe, 0))), (os.path.dirname(exe), exe))
        # A Windows Installer product: its icon is in Windows' cache, its uninstaller in its own folder
        cached = self.file("Windows", "Installer", "{GUID}", "icon.exe")
        unins = self.file("Apps", "Other", "unins000.exe")
        program = Program("k", "Other", icon=(cached, 0), uninstall=f'"{unins}" /SILENT')
        self.assertEqual(uninstaller.program_location(program), (os.path.dirname(unins), None))

    def test_unknown_or_gone(self):
        self.assertIsNone(uninstaller.program_location(Program("k", "Tool")))
        self.assertIsNone(uninstaller.program_location(Program("k", "Tool", location=os.path.join(self.root, "gone"))))
        self.assertIsNone(uninstaller.program_location(Program("k", "Tool", location=self.windows)))
        self.assertIsNone(uninstaller.program_location(Program("k", "Tool", location=r"\\server\share\Tool",
                                                               uninstall="MsiExec.exe /X{GUID}")))


class RemovedElsewhere(unittest.TestCase):
    """Programs removed through Windows' settings or their own uninstaller, found by the list kept from last time."""

    def setUp(self):
        self.data = tempfile.mkdtemp(prefix="simpletool-known-test-")
        self.patch = mock.patch.object(uninstaller.engine, "data_dir", lambda: self.data)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        shutil.rmtree(self.data, ignore_errors=True)

    def test_programs_gone_since_the_last_time(self):
        tool = Program(r"HKCU\Uninstall\Tool", "Good Tool", "Acme", location=r"C:\Tools\Good Tool",
                       icon=(r"C:\Tools\Good Tool\tool.exe", 0), user=True)
        other = Program(r"HKLM\Uninstall\Other", "Other")
        self.assertEqual(uninstaller.removed_elsewhere([tool, other]), [], "nothing to compare with the first time")
        self.assertEqual(uninstaller.removed_elsewhere([tool, other]), [])
        gone = uninstaller.removed_elsewhere([other])
        self.assertEqual([(p.key, p.name, p.publisher, p.location, p.icon, p.user) for p, day in gone],
                         [(tool.key, "Good Tool", "Acme", r"C:\Tools\Good Tool", (r"C:\Tools\Good Tool\tool.exe", 0),
                           True)])
        self.assertEqual(gone[0][1], datetime.date.today())
        # Offered again the next time, until it is forgotten
        self.assertEqual([p.key for p, day in uninstaller.removed_elsewhere([other])], [tool.key])
        uninstaller.forget(tool.key)
        self.assertEqual(uninstaller.removed_elsewhere([other]), [])

    def test_installed_again(self):
        tool = Program("k1", "Good Tool")
        uninstaller.removed_elsewhere([tool])
        self.assertEqual(len(uninstaller.removed_elsewhere([])), 1)
        self.assertEqual(uninstaller.removed_elsewhere([tool]), [], "back in the list")
        self.assertEqual(uninstaller.removed_elsewhere([tool]), [])

    def test_a_program_simpletool_removed_is_not_offered(self):
        tool = Program("k1", "Good Tool")
        uninstaller.removed_elsewhere([tool])
        uninstaller.forget(tool.key)  # SimpleTool ran its uninstaller and showed what it left
        self.assertEqual(uninstaller.removed_elsewhere([]), [])

    def test_a_damaged_file_starts_over(self):
        with open(os.path.join(self.data, "programs.json"), "w") as f:
            f.write("{not json")
        self.assertEqual(uninstaller.removed_elsewhere([Program("k", "Tool")]), [])
        self.assertEqual(len(uninstaller.removed_elsewhere([])), 1)


class Removing(unittest.TestCase):
    def test_what_needs_administrator_rights(self):
        with mock.patch.dict(os.environ, {"USERPROFILE": PROFILE}):
            own = [{"kind": "folder", "path": rf"{PROFILE}\AppData\Roaming\Tool", "name": "", "size": 1},
                   {"kind": "key", "path": r"HKCU\Software\Tool", "name": "", "size": 0},
                   {"kind": "value", "path": r"HKCU\Software\Microsoft\Windows\CurrentVersion\Run", "name": "Tool",
                    "size": 0}]
            self.assertFalse(uninstaller.needs_admin(own))
            self.assertTrue(uninstaller.needs_admin(own + [{"kind": "key", "path": r"HKLM\SOFTWARE\Tool", "name": "",
                                                            "size": 0}]))
            self.assertTrue(uninstaller.needs_admin([{"kind": "folder", "path": r"C:\Program Files\Tool", "name": "",
                                                      "size": 1}]))

    def test_network_paths_are_not_checked(self):
        # A share of a computer that is off keeps a check waiting: unknown, never "missing"
        self.assertFalse(uninstaller._local(r"\\server\share\tool\unins000.exe"))
        self.assertFalse(uninstaller._local("tool.exe"))
        self.assertTrue(uninstaller._local(os.environ.get("SystemRoot", r"C:\Windows")))
        self.assertFalse(Program("k", "Tool", uninstall=r'"\\server\share\unins000.exe"').uninstaller_missing)

    def test_keys_are_saved_files_go_to_the_bin(self):
        with tempfile.TemporaryDirectory() as data:
            calls = []
            program = Program("k", "Good Tool")
            leftovers = [{"kind": "key", "path": r"HKCU\Software\Good Tool", "name": "", "size": 0},
                         {"kind": "value", "path": r"HKCU\Software\Microsoft\Windows\CurrentVersion\Run",
                          "name": "Good Tool", "size": 0},
                         {"kind": "folder", "path": rf"{PROFILE}\AppData\Roaming\Good Tool", "name": "", "size": 5}]
            with mock.patch.object(uninstaller.engine, "data_dir", lambda: data), \
                    mock.patch.object(uninstaller.engine, "run", lambda args: calls.append(("run", args))), \
                    mock.patch.object(uninstaller.engine, "delete_tree", lambda path: calls.append(("tree", path))), \
                    mock.patch.object(uninstaller.engine, "read_value", lambda path, name: ('"C:\\x.exe"', 1)), \
                    mock.patch.object(uninstaller.engine, "delete_value",
                                      lambda path, name: calls.append(("value", name))), \
                    mock.patch.object(uninstaller, "to_recycle_bin", lambda path: calls.append(("bin", path))):
                folder, errors = uninstaller.remove_leftovers(program, leftovers)
            self.assertEqual(errors, [])
            self.assertEqual(calls[0][0], "run")
            self.assertEqual(calls[0][1][:3], ["reg.exe", "export", r"HKCU\Software\Good Tool"], "exported first")
            self.assertEqual([c[0] for c in calls], ["run", "tree", "value", "bin"])
            with open(os.path.join(folder, "removed.json"), encoding="utf-8") as f:
                saved = json.load(f)
            self.assertEqual(saved["values"][0]["data"], '"C:\\x.exe"')
            self.assertEqual(len(saved["removed"]), 3)


class Icons(unittest.TestCase):
    def test_a_program_icon_with_transparency(self):
        notepad = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "notepad.exe")
        data = uninstaller.icon_png(notepad, 0, 32)
        self.assertTrue(data.startswith(b"\x89PNG\r\n\x1a\n"))
        self.assertEqual(struct.unpack(">II", data[16:24]), (32, 32))
        # One IDAT chunk of rows, each a filter byte and 32 RGBA pixels: the corners are see-through, the middle not
        length = struct.unpack(">I", data[33:37])[0]
        rows = zlib.decompress(data[41:41 + length])
        alpha = [rows[y * 129 + 1 + x * 4 + 3] for y in range(32) for x in range(32)]
        self.assertEqual(alpha[0], 0, "a corner")
        self.assertGreater(max(alpha), 200, "the picture")
        self.assertIsNone(uninstaller.icon_png(os.path.join(notepad, "missing.exe"), 0, 32))

    def test_png(self):
        data = raster.png(2, 1, bytes([255, 0, 0, 255, 0, 0, 255, 128]))
        self.assertTrue(data.startswith(b"\x89PNG\r\n\x1a\n"))
        self.assertEqual(struct.unpack(">II", data[16:24]), (2, 1))


class Uninstaller(unittest.TestCase):
    def test_waits_for_what_the_uninstaller_starts(self):
        # Like Inno Setup: the uninstaller starts a copy of itself and quits at once; the copy does the work
        program = Program("k", "Demo", uninstall='cmd.exe /c start "" /b cmd.exe /c ping -n 2 127.0.0.1 ^>nul & exit 3')
        start = time.monotonic()
        code = uninstaller.run_uninstaller(program)
        self.assertEqual(code, 3)
        self.assertGreater(time.monotonic() - start, 0.8, "the second program was waited for")


if __name__ == "__main__":
    unittest.main()
