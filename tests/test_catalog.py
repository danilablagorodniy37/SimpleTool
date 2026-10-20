"""Static audit of the tweak catalog: no tweak touches anything that could break Windows."""
import re
import unittest
import winreg

import engine
import tweaks
from engine import ABSENT, OwnedKey, Service, Shortcut, Task, Value

ALL_OPS = [(tweak, op) for tweak in tweaks.TWEAKS for op in tweak.ops]
VALUES = [(tweak, op) for tweak, op in ALL_OPS if isinstance(op, Value)]

# Keys and values whose change can break Windows boot, sign-in, protection or updates
DANGEROUS_PATHS = [
    r"\\Winlogon", r"\\Image File Execution Options", r"\\SafeBoot", r"\\Session Manager",
    r"\\CurrentVersion\\Run", r"\\Windows Defender", r"\\WindowsUpdate", r"\\Lsa\b", r"\\SecurityProviders",
    r"\\Control\\Class\\", r"\\Policies\\System$", r"\\Terminal Server", r"\\BCD00000000",
]
DANGEROUS_NAMES = {"EnableLUA", "ConsentPromptBehaviorAdmin", "PromptOnSecureDesktop", "DisableAntiSpyware",
                   "SmartScreenEnabled", "EnableSmartScreen", "SaveZoneInformation", "Shell", "Userinit",
                   "AppInit_DLLs", "ImagePath", "Debugger", "LargeSystemCache", "Hidden", "ShowSuperHidden"}
# Writes to HKLM\SYSTEM are allowed only here: everything else there is the Windows core
SYSTEM_ALLOWED = [
    r"HKLM\SYSTEM\CurrentControlSet\Control\WMI\Autologger\Diagtrack-Listener|Start",
    r"HKLM\SYSTEM\CurrentControlSet\Control\FileSystem|LongPathsEnabled",
    r"HKLM\SYSTEM\CurrentControlSet\Control\Power\PowerSettings\7516b95f-f776-4464-8c53-06167f40cc99"
    r"\8EC4B3A5-6868-48c2-BE75-4F3044BE88A7|Attributes",
]
SERVICES_ALLOWED = {"DiagTrack", "dmwappushservice", "NvTelemetryContainer"}
# Tasks without which Windows does not update, protect or maintain itself
TASKS_FORBIDDEN = ["UpdateOrchestrator", "WindowsUpdate", "Windows Defender", "Windows Error Reporting\\QueueReporting",
                   "TaskScheduler", "Registry\\RegIdleBackup", "SystemRestore", "Time Synchronization", "BitLocker"]
TASK_PREFIXES = ("microsoft\\windows\\", "microsoft\\office\\", "nvtm")
# Owned keys that tweaks create and delete on revert
OWNED_ALLOWED = [
    r"HKLM\SOFTWARE\Classes\.cmd\ShellNew", r"HKLM\SOFTWARE\Classes\.reg\ShellNew",
    r"HKLM\SOFTWARE\Classes\Applications\photoviewer.dll\shell\open",
    r"HKCU\Software\Classes\Unknown\shell\edit", r"HKCU\Software\Classes\MSInfoFile\shell\open",
]
FORBIDDEN_IN_COMMANDS = [r"\bdel\b", r"\brd\b", r"\brmdir\b", r"\bformat\b", r"reg(\.exe)? delete",
                         r"shutdown[^&]*\s/f\b",  # forced closing of programs without saving
                         r"\bdiskpart\b", r"bcdedit\s*/delete\b", r"Remove-Item", r"\bvssadmin\b",
                         r"Set-MpPreference", r"\bnet\s+user\b"]


def commands():
    """Menu item commands: (Default) values of ...\\command keys."""
    for tweak, op in VALUES:
        if op.path.lower().endswith("\\command") and op.name == "" and isinstance(op.data, str):
            yield tweak, op.data


class CatalogSafety(unittest.TestCase):
    def test_ids_are_unique_and_categories_known(self):
        ids = [t.id for t in tweaks.TWEAKS]
        self.assertEqual(len(ids), len(set(ids)))
        for tweak in tweaks.TWEAKS:
            self.assertIn(tweak.category, tweaks.CATEGORIES, tweak.id)
            self.assertTrue(tweak.ops, tweak.id)

    def test_registry_paths_use_known_hives(self):
        for tweak, op in ALL_OPS:
            path = getattr(op, "path", None)
            if path and not isinstance(op, (Task,)):
                self.assertRegex(path, r"^(HKLM|HKCU)\\", f"{tweak.id}: {path}")

    def test_no_writes_to_dangerous_locations(self):
        for tweak, op in VALUES:
            with self.subTest(tweak=tweak.id, value=str(op)):
                for pattern in DANGEROUS_PATHS:
                    self.assertNotRegex(op.path, f"(?i){pattern}")
                self.assertNotIn(op.name, DANGEROUS_NAMES)

    def test_system_hive_writes_are_allowlisted(self):
        for tweak, op in VALUES:
            if op.path.upper().startswith(r"HKLM\SYSTEM"):
                self.assertIn(f"{op.path}|{op.name}", SYSTEM_ALLOWED, tweak.id)

    def test_only_telemetry_services_are_touched(self):
        for tweak, op in ALL_OPS:
            if isinstance(op, Service):
                self.assertIn(op.name, SERVICES_ALLOWED, tweak.id)
                self.assertIn(op.default_start, (2, 3), f"{op.name}: revert must re-enable the service")

    def test_only_known_data_collection_tasks_are_touched(self):
        for tweak, op in ALL_OPS:
            if isinstance(op, Task):
                with self.subTest(task=op.path):
                    self.assertTrue(op.path.lower().startswith(TASK_PREFIXES))
                    for forbidden in TASKS_FORBIDDEN:
                        self.assertNotIn(forbidden.lower(), op.path.lower())

    def test_deleted_keys_belong_to_simpletool(self):
        """Revert deletes only what SimpleTool itself created."""
        for tweak, op in ALL_OPS:
            if isinstance(op, OwnedKey):
                with self.subTest(key=op.path):
                    self.assertTrue("\\SimpleTool." in op.path or op.path in OWNED_ALLOWED)
                    self.assertNotRegex(op.path, r"(?i)\\(Drive|Folder|AllFilesystemObjects)\\shell\\")

    def test_value_types_match_data(self):
        for tweak, op in VALUES:
            with self.subTest(value=str(op)):
                for data in (op.data, op.default):
                    if data is ABSENT or callable(data):
                        continue
                    if op.kind == winreg.REG_DWORD:
                        self.assertIsInstance(data, int)
                        self.assertTrue(0 <= data <= 0xFFFFFFFF)
                    else:
                        self.assertIn(op.kind, (winreg.REG_SZ, winreg.REG_EXPAND_SZ))
                        self.assertIsInstance(data, str)
                if callable(op.data):
                    self.assertFalse(op.check, "labels change with the language and must not decide the status")

    def test_menu_commands_never_force_or_delete(self):
        for tweak, command in commands():
            with self.subTest(tweak=tweak.id, command=command[:60]):
                for pattern in FORBIDDEN_IN_COMMANDS:
                    self.assertNotRegex(command, f"(?i){pattern}")

    def test_restart_commands_only_where_expected_and_elevated(self):
        for tweak, command in commands():
            if "shutdown" in command.lower() or "bcdedit" in command.lower():
                self.assertEqual(tweak.id, "this_pc_tools")
                self.assertIn("-Verb RunAs", command, "needs a UAC prompt before restarting")
        shortcuts = [op for t in tweaks.TWEAKS for op in t.ops if isinstance(op, Shortcut)]
        for op in shortcuts:
            self.assertNotIn("/f", op.args.split(), "restart shortcut must not force-close programs")

    def test_admin_commands_ask_for_elevation(self):
        for tweak, command in commands():
            if re.search(r"(?i)\b(netsh|takeown|icacls|bcdedit)\b", command):
                self.assertIn("Start-Process cmd.exe -Verb RunAs", command, tweak.id)

    def test_restore_point_script_does_not_change_frequency_limit(self):
        self.assertNotIn("SystemRestorePointCreationFrequency", engine.RESTORE_POINT_SCRIPT)
        self.assertNotIn("Set-", engine.RESTORE_POINT_SCRIPT)


if __name__ == "__main__":
    unittest.main()
