"""The PC's specifications for a problem report: read without rights, and never a reason for the report to fail."""
import unittest
from unittest import mock

import sysinfo


class SystemInfo(unittest.TestCase):
    def test_this_pc(self):
        lines = sysinfo.summary("SimpleTool: test")
        self.assertEqual(lines[0], "SimpleTool: test")
        for prefix in ("Windows: Windows 1", "Processor: ", "Graphics: ", "Memory: "):
            self.assertTrue(any(line.startswith(prefix) for line in lines), prefix)
        self.assertFalse(any("  " in line for line in lines), "padding from the registry is trimmed")

    def test_unreadable_registry(self):
        def refuse(*args, **kwargs):
            raise PermissionError(5, "Access is denied")
        with mock.patch.object(sysinfo.winreg, "OpenKey", refuse):
            lines = sysinfo.summary("SimpleTool: test")
        self.assertIn("Processor: unknown", lines)
        self.assertIn("Graphics: unknown", lines)
        self.assertTrue(lines[1].startswith("Windows: Windows "))

    def test_windows_names(self):
        values = {"CurrentBuild": "22631", "UBR": 4317, "EditionID": "Core", "DisplayVersion": "23H2"}
        with mock.patch.object(sysinfo, "_value", lambda path, name: str(values[name]) if name in values else None):
            self.assertEqual(sysinfo.windows(), "Windows 11 Home 23H2, build 22631.4317")
        values.update(CurrentBuild="19045", EditionID="Professional", DisplayVersion="22H2")
        with mock.patch.object(sysinfo, "_value", lambda path, name: str(values[name]) if name in values else None):
            self.assertEqual(sysinfo.windows(), "Windows 10 Pro 22H2, build 19045.4317")


if __name__ == "__main__":
    unittest.main()
