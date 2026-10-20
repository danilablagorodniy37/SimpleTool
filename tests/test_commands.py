"""Context menu commands pass the "registry -> PowerShell -> cmd" chain without breaking quotes.

Elevated starts (Start-Process ... -Verb RunAs) are replaced with printing the arguments, the clipboard
is not touched: the test changes nothing on the system.
"""
import hashlib
import os
import shutil
import subprocess
import tempfile
import unittest

import engine
import tweaks
from engine import Value

PNG = bytes.fromhex("89504e470d0a1a0a0000000d4948445200000001000000010806000000"
                    "1f15c4890000000d49444154789c6360f8cf000000030101005d6b1a4e0000000049454e44ae426082")


def menu_commands():
    for tweak in tweaks.TWEAKS:
        for op in tweak.ops:
            if isinstance(op, Value) and op.path.lower().endswith("\\command") and op.name == "" \
                    and isinstance(op.data, str) and "powershell" in op.data:
                yield tweak.id, op.data


def dry_run(command):
    safe = (command.replace("Start-Process cmd.exe -Verb RunAs -WindowStyle Hidden -ArgumentList", "Write-Output")
                   .replace("Start-Process cmd.exe -Verb RunAs -ArgumentList", "Write-Output")
                   .replace("| Set-Clipboard", "")
                   .replace("[System.Windows.Clipboard]::SetImage(", "Write-Output ("))
    assert "Start-Process" not in safe and "Set-Clipboard" not in safe and "SetImage" not in safe
    # PowerShell writes to the pipe in the OEM code page; switch output to UTF-8 to check Cyrillic in paths
    safe = safe.replace('-Command "', '-Command "[Console]::OutputEncoding = [Text.Encoding]::UTF8; ', 1)
    # A regular PC environment: default Windows PowerShell module paths (see engine.clean_env)
    result = subprocess.run(safe, capture_output=True, encoding="utf-8", errors="replace", timeout=60,
                            env=engine.clean_env())
    return result.returncode, (result.stdout + result.stderr).strip()


class MenuCommands(unittest.TestCase):
    # Explorer pastes the path into the command as is. The second name would run code if the path became part of
    # PowerShell code: ' closes a quoted string, ( ) and $( ) evaluate, ; starts a new command
    NAMES = ["Тестовый файл [1] & co.png", "Mom's photo (1) $(7331+1) ; echo 7333 #.png"]

    @classmethod
    def setUpClass(cls):
        cls.folder = tempfile.mkdtemp(prefix="simpletool cmd test ")
        cls.paths = [os.path.join(cls.folder, name) for name in cls.NAMES]
        for path in cls.paths:
            with open(path, "wb") as f:
                f.write(PNG)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.folder, ignore_errors=True)

    def test_paths_survive_quoting(self):
        commands = list(menu_commands())
        self.assertGreater(len(commands), 10)
        for path in self.paths:
            for tweak_id, command in commands:
                with self.subTest(tweak=tweak_id, command=command[:70], path=os.path.basename(path)):
                    code, out = dry_run(command.replace("%1", path))
                    self.assertEqual(code, 0, out)
                    self.assertNotIn("7332", out, "the path was run as code")
                    self.assertNotIn("7333\n", out + "\n", "the path was run as code")
                    if tweak_id in ("take_ownership", "firewall"):
                        self.assertTrue(out.startswith("/c "), out)
                    if tweak_id == "take_ownership":
                        self.assertIn(f'"{path}"', out, "the path must reach cmd.exe as one quoted argument")
                    if tweak_id == "firewall":
                        self.assertIn(f'name="SimpleTool - {path}"', out)
                        if "add rule" in out:
                            self.assertIn(f'program="{path}"', out)
                    if tweak_id == "file_hash":
                        algorithm = next(a for a in ("SHA512", "SHA384", "SHA256", "SHA1", "MD5") if a in command)
                        self.assertEqual(out, hashlib.new(algorithm.lower(), PNG).hexdigest())
                    if tweak_id == "copy_image":
                        self.assertIn("UriSource", out)

    def test_path_is_never_part_of_powershell_code(self):
        for tweak_id, command in menu_commands():
            if "%1" in command:
                with self.subTest(tweak=tweak_id):
                    self.assertTrue(command.startswith('cmd.exe /d /c set "SIMPLETOOL_PATH=%1" & '), command)
                    self.assertEqual(command.count("%1"), 1)

    def test_safe_mode_commands_keep_braces(self):
        for tweak_id, command in menu_commands():
            if "bcdedit" in command:
                code, out = dry_run(command)
                self.assertEqual(code, 0, out)
                self.assertIn("{current}", out)
                self.assertIn("shutdown /r /t 0", out)


if __name__ == "__main__":
    unittest.main()
