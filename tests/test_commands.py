"""Команды пунктов контекстного меню проходят цепочку «реестр → PowerShell → cmd» без порчи кавычек.

Запуск с повышением прав (Start-Process ... -Verb RunAs) заменяется выводом аргументов, буфер обмена
не трогается: тест ничего не меняет в системе.
"""
import hashlib
import os
import shutil
import subprocess
import tempfile
import unittest

import tweaks
from engine import Value

PNG = bytes.fromhex("89504e470d0a1a0a0000000d4948445200000001000000010806000000"
                    "1f15c4890000000d49444154789c6360f8cf000000030101005d6b1a4e0000000049454e44ae426082")


def menu_commands():
    for tweak in tweaks.TWEAKS:
        for op in tweak.ops:
            if isinstance(op, Value) and op.path.lower().endswith("\\command") and op.name == "" \
                    and isinstance(op.data, str) and op.data.startswith("powershell"):
                yield tweak.id, op.data


def dry_run(command):
    safe = (command.replace("Start-Process cmd.exe -Verb RunAs -WindowStyle Hidden -ArgumentList", "Write-Output")
                   .replace("Start-Process cmd.exe -Verb RunAs -ArgumentList", "Write-Output")
                   .replace("| Set-Clipboard", "")
                   .replace("[System.Windows.Clipboard]::SetImage(", "Write-Output ("))
    assert "Start-Process" not in safe and "Set-Clipboard" not in safe and "SetImage" not in safe
    # PowerShell пишет в канал в кодировке OEM; для проверки кириллицы в путях переключаем вывод на UTF-8
    safe = safe.replace('-Command "', '-Command "[Console]::OutputEncoding = [Text.Encoding]::UTF8; ', 1)
    result = subprocess.run(safe, capture_output=True, encoding="utf-8", errors="replace", timeout=60)
    return result.returncode, (result.stdout + result.stderr).strip()


class MenuCommands(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder = tempfile.mkdtemp(prefix="simpletool cmd test ")
        cls.path = os.path.join(cls.folder, "Тестовый файл [1] & co.png")
        with open(cls.path, "wb") as f:
            f.write(PNG)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.folder, ignore_errors=True)

    def test_paths_survive_quoting(self):
        commands = list(menu_commands())
        self.assertGreater(len(commands), 10)
        for tweak_id, command in commands:
            with self.subTest(tweak=tweak_id, command=command[:70]):
                code, out = dry_run(command.replace("%1", self.path))
                self.assertEqual(code, 0, out)
                if tweak_id in ("take_ownership", "firewall"):
                    self.assertTrue(out.startswith("/c "), out)
                if tweak_id == "take_ownership":
                    self.assertIn(f'"{self.path}"', out, "the path must reach cmd.exe as one quoted argument")
                if tweak_id == "firewall":
                    self.assertIn(f'name="SimpleTool - {self.path}"', out)
                    if "add rule" in out:
                        self.assertIn(f'program="{self.path}"', out)
                if tweak_id == "file_hash":
                    algorithm = next(a for a in ("SHA512", "SHA384", "SHA256", "SHA1", "MD5") if a in command)
                    self.assertEqual(out, hashlib.new(algorithm.lower(), PNG).hexdigest())
                if tweak_id == "copy_image":
                    self.assertIn("UriSource", out)

    def test_safe_mode_commands_keep_braces(self):
        for tweak_id, command in menu_commands():
            if "bcdedit" in command:
                code, out = dry_run(command)
                self.assertEqual(code, 0, out)
                self.assertIn("{current}", out)
                self.assertIn("shutdown /r /t 0", out)


if __name__ == "__main__":
    unittest.main()
