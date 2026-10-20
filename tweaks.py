"""Каталог твиков. Значения реестра сверены с базой «ТВикинариум» и проверены под Windows 10/11."""
import os
from winreg import REG_DWORD, REG_EXPAND_SZ, REG_SZ

from engine import OwnedKey, Service, Shortcut, Task, Tweak, Value
from i18n import TEXTS, menu_label

CATEGORIES = ["privacy", "system", "explorer", "context"]

HKCU_CLASSES = r"HKCU\Software\Classes"
HKLM_CLASSES = r"HKLM\SOFTWARE\Classes"
POLICIES = r"HKLM\SOFTWARE\Policies\Microsoft\Windows"
EXPLORER = r"HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer"
ADVANCED = EXPLORER + r"\Advanced"
THIS_PC = HKCU_CLASSES + r"\CLSID\{20D04FE0-3AEA-1069-A2D8-08002B30309D}\shell"


def elevated(args, hidden=True):
    """Команда пункта меню, которая запускает cmd.exe /c ... от имени администратора."""
    style = " -WindowStyle Hidden" if hidden else ""
    return ('powershell.exe -NoProfile -WindowStyle Hidden -Command "Start-Process cmd.exe -Verb RunAs'
            f"{style} -ArgumentList '{args}'\"")


def menu_item(path, label, command, icon=None, extended=False, shield=False, kind=REG_SZ):
    """Пункт контекстного меню: свой ключ с подписью, значком и командой."""
    ops = [OwnedKey(path), Value(path, "MUIVerb", label, REG_SZ, check=False)]
    if icon:
        ops.append(Value(path, "Icon", icon, REG_SZ))
    if extended:
        ops.append(Value(path, "Extended", "", REG_SZ))  # только с Shift
    if shield:
        ops.append(Value(path, "HasLUAShield", "", REG_SZ))
    ops.append(Value(path + r"\command", "", command, kind))
    return ops


def submenu(path, label, icon, items):
    """Вложенное меню: items — список (имя ключа, подпись, команда)."""
    ops = [OwnedKey(path), Value(path, "MUIVerb", label, REG_SZ, check=False),
           Value(path, "Icon", icon, REG_SZ), Value(path, "SubCommands", "", REG_SZ)]
    for name, item_label, command in items:
        ops += menu_item(rf"{path}\shell\{name}", item_label, command)
    return ops


def photo_viewer_installed():
    return os.path.exists(os.path.expandvars(r"%ProgramFiles%\Windows Photo Viewer\PhotoViewer.dll"))


# --- Конфиденциальность ---

DATA_COLLECTION_TASKS = [
    r"Microsoft\Windows\Maintenance\WinSAT",
    r"Microsoft\Windows\Autochk\Proxy",
    r"Microsoft\Windows\Application Experience\Microsoft Compatibility Appraiser",
    r"Microsoft\Windows\Application Experience\Microsoft Compatibility Appraiser Exp",  # имя в Windows 11
    r"Microsoft\Windows\Application Experience\ProgramDataUpdater",
    r"Microsoft\Windows\Application Experience\StartupAppTask",
    r"Microsoft\Windows\PI\Sqm-Tasks",
    r"Microsoft\Windows\NetTrace\GatherNetworkInfo",
    r"Microsoft\Windows\Customer Experience Improvement Program\Consolidator",
    r"Microsoft\Windows\Customer Experience Improvement Program\KernelCeipTask",
    r"Microsoft\Windows\Customer Experience Improvement Program\UsbCeip",
    r"Microsoft\Windows\DiskDiagnostic\Microsoft-Windows-DiskDiagnosticResolver",
    r"Microsoft\Windows\DiskDiagnostic\Microsoft-Windows-DiskDiagnosticDataCollector",
]

OFFICE_TELEMETRY_TASKS = [
    r"Microsoft\Office\Office ClickToRun Service Monitor",
    r"Microsoft\Office\OfficeTelemetry\AgentFallBack2016",
    r"Microsoft\Office\OfficeTelemetry\OfficeTelemetryAgentLogOn2016",
    r"Microsoft\Office\OfficeTelemetryAgentFallBack2016",
    r"Microsoft\Office\OfficeTelemetryAgentLogOn2016",
    r"Microsoft\Office\OfficeTelemetryAgentFallBack",
    r"Microsoft\Office\OfficeTelemetryAgentLogOn",
    r"Microsoft\Office\Office 15 Subscription Heartbeat",
]

NVIDIA_TASKS = [f"{name}_{{B2FE1952-0186-46C3-BAEC-A80AA35AC5B8}}" for name in ("NvTmRepOnLogon", "NvTmRep", "NvTmMon")]

SYNC_GROUPS = ["Accessibility", "BrowserSettings", "Credentials", "Language", "Personalization", "Windows"]

PRIVACY = [
    Tweak("ads", "privacy", [
        Value(r"HKCU\Software\Microsoft\Windows\CurrentVersion\AdvertisingInfo", "Enabled", 0, default=1),
    ]),
    Tweak("sync", "privacy", [
        Value(rf"HKCU\Software\Microsoft\Windows\CurrentVersion\SettingSync\Groups\{group}", "Enabled", 0)
        for group in SYNC_GROUPS
    ]),
    Tweak("telemetry", "privacy", [
        Value(r"HKLM\SYSTEM\CurrentControlSet\Control\WMI\Autologger\Diagtrack-Listener", "Start", 0, default=1),
        Service("DiagTrack", default_start=2),
        Service("dmwappushservice", default_start=3),
    ] + [Task(path) for path in OFFICE_TELEMETRY_TASKS]),
    Tweak("nvidia", "privacy", [Service("NvTelemetryContainer", default_start=2)] + [Task(p) for p in NVIDIA_TASKS]),
    Tweak("data_tasks", "privacy", [Task(path) for path in DATA_COLLECTION_TASKS]),
    Tweak("inventory", "privacy", [
        Value(POLICIES + r"\AppCompat", "DisableInventory", 1),
    ]),
    Tweak("diagnostics", "privacy", [
        Value(r"HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\DataCollection", "AllowTelemetry", 0),
        Value(POLICIES + r"\DataCollection", "AllowTelemetry", 0),
        Value(POLICIES + r"\AppCompat", "AITEnable", 0),
    ]),
    Tweak("handwriting", "privacy", [
        Value(POLICIES + r"\TabletPC", "PreventHandwritingDataSharing", 1),
        Value(POLICIES + r"\HandwritingErrorReports", "PreventHandwritingErrorReports", 1),
        Value(r"HKCU\Software\Microsoft\Input\TIPC", "Enabled", 0, default=1),
    ]),
    Tweak("steps_recorder", "privacy", [
        Value(POLICIES + r"\AppCompat", "DisableUAR", 1),
        Value(POLICIES + r"\Personalization", "NoLockScreenCamera", 1),
    ]),
    Tweak("location", "privacy", [
        Value(POLICIES + r"\LocationAndSensors", name, 1)
        for name in ("DisableLocation", "DisableLocationScripting", "DisableWindowsLocationProvider")
    ]),
    Tweak("feedback", "privacy", [
        Value(r"HKCU\Software\Microsoft\Siuf\Rules", "NumberOfSIUFInPeriod", 0),
        Value(r"HKCU\Software\Microsoft\Siuf\Rules", "PeriodInNanoSeconds", 0),
        Value(POLICIES + r"\DataCollection", "DoNotShowFeedbackNotifications", 1),
    ]),
    Tweak("speech", "privacy", [
        Value(r"HKLM\SOFTWARE\Policies\Microsoft\Speech", "AllowSpeechModelUpdate", 0),
    ]),
    Tweak("experiments", "privacy", [
        Value(r"HKLM\SOFTWARE\Microsoft\PolicyManager\current\device\System", "AllowExperimentation", 0),
    ]),
]

# --- Система ---

PHOTO_VIEWER_TYPES = [".bmp", ".dib", ".gif", ".ico", ".jfif", ".jpe", ".jpeg", ".jpg", ".png", ".tga"]
PHOTO_VIEWER_OPEN = HKLM_CLASSES + r"\Applications\photoviewer.dll\shell\open"

SYSTEM = [
    Tweak("startup_delay", "system", [
        Value(EXPLORER + r"\Serialize", "Startupdelayinmsec", 0),
    ]),
    Tweak("autoplay", "system", [
        Value(EXPLORER + r"\AutoplayHandlers", "DisableAutoplay", 1, default=0),
    ]),
    Tweak("layout_hotkey", "system", [
        Value(r"HKCU\Keyboard Layout\Toggle", "Hotkey", "2", REG_SZ, default="1"),
        Value(r"HKCU\Keyboard Layout\Toggle", "Language Hotkey", "2", REG_SZ, default="1"),
        Value(r"HKCU\Keyboard Layout\Toggle", "Layout Hotkey", "3", REG_SZ, default="2"),
    ]),
    Tweak("photo_viewer", "system", [
        OwnedKey(PHOTO_VIEWER_OPEN),
        Value(PHOTO_VIEWER_OPEN, "MuiVerb", "@photoviewer.dll,-3043", REG_SZ),
        Value(PHOTO_VIEWER_OPEN + r"\command", "",
              r'%SystemRoot%\System32\rundll32.exe "%ProgramFiles%\Windows Photo Viewer\PhotoViewer.dll", '
              r"ImageView_Fullscreen %1", REG_EXPAND_SZ),
    ] + [
        Value(r"HKLM\SOFTWARE\Microsoft\Windows Photo Viewer\Capabilities\FileAssociations", ext,
              "PhotoViewer.FileAssoc.Tiff", REG_SZ)
        for ext in PHOTO_VIEWER_TYPES
    ], requires=photo_viewer_installed),
    Tweak("lock_timeout", "system", [
        Value(r"HKLM\SYSTEM\CurrentControlSet\Control\Power\PowerSettings\7516b95f-f776-4464-8c53-06167f40cc99"
              r"\8EC4B3A5-6868-48c2-BE75-4F3044BE88A7", "Attributes", 2, default=1),
    ]),
    Tweak("desktop_shortcuts", "system", [
        Shortcut({lang: TEXTS[lang]["menu"]["shortcut_restart"] for lang in TEXTS},
                 r"%SystemRoot%\System32\shutdown.exe", "/r /t 0", r"%SystemRoot%\System32\shell32.dll,27"),
        Shortcut({lang: TEXTS[lang]["menu"]["shortcut_refresh"] for lang in TEXTS},
                 r"%SystemRoot%\System32\ie4uinit.exe", "-show", r"%SystemRoot%\System32\shell32.dll,238"),
    ]),
]

# --- Проводник ---

EXPLORER_TWEAKS = [
    Tweak("file_extensions", "explorer", [Value(ADVANCED, "HideFileExt", 0, default=1)]),
    Tweak("open_this_pc", "explorer", [Value(ADVANCED, "LaunchTo", 1)]),
    Tweak("empty_drives", "explorer", [Value(ADVANCED, "HideDrivesWithNoMedia", 0)]),
    Tweak("long_paths", "explorer", [
        Value(r"HKLM\SYSTEM\CurrentControlSet\Control\FileSystem", "LongPathsEnabled", 1, default=0),
    ]),
    Tweak("restore_folders", "explorer", [Value(ADVANCED, "PersistBrowsers", 1)]),
    Tweak("recent_history", "explorer", [
        Value(EXPLORER, "ShowFrequent", 0),
        Value(EXPLORER, "ShowRecent", 0),
        Value(ADVANCED, "Start_TrackDocs", 0, default=1),
        Value(ADVANCED, "Start_TrackProgs", 0, default=1),
    ]),
    Tweak("menu_delay", "explorer", [
        Value(r"HKCU\Control Panel\Desktop", "MenuShowDelay", "20", REG_SZ, default="400"),
    ]),
]

# --- Контекстное меню ---
# Пункты пишутся в HKCU\Software\Classes под своими именами SimpleTool.*, чтобы откат удалял только их.

ADMINS = "*S-1-5-32-544"  # группа «Администраторы» по SID, не зависит от языка Windows
HASHES = ["MD5", "SHA1", "SHA256", "SHA384", "SHA512"]
IMAGE_TYPES = [".bmp", ".gif", ".ico", ".jpeg", ".jpg", ".png", ".tif", ".tiff"]
FIREWALL_RULE = r'name=\"SimpleTool - %1\"'


def hash_command(algorithm):
    return ('powershell.exe -NoProfile -WindowStyle Hidden -Command '
            f"\"(Get-FileHash -Algorithm {algorithm} -LiteralPath '%1').Hash.ToLower() | Set-Clipboard\"")


COPY_IMAGE_COMMAND = ('powershell.exe -NoProfile -WindowStyle Hidden -STA -Command "Add-Type -AssemblyName PresentationCore; '
                      "[System.Windows.Clipboard]::SetImage((New-Object System.Windows.Media.Imaging.BitmapImage ([Uri]'%1')))\"")

SAFE_MODE = [
    ("1Normal", menu_label("restart_normal"), elevated(
        "/c bcdedit /deletevalue {current} safeboot & bcdedit /deletevalue {current} safebootalternateshell & shutdown /r /t 0")),
    ("2Safe", menu_label("restart_safe"), elevated(
        "/c bcdedit /set {current} safeboot minimal && shutdown /r /t 0")),
    ("3Network", menu_label("restart_network"), elevated(
        "/c bcdedit /set {current} safeboot network && shutdown /r /t 0")),
    ("4Cmd", menu_label("restart_cmd"), elevated(
        "/c bcdedit /set {current} safeboot minimal && bcdedit /set {current} safebootalternateshell yes && shutdown /r /t 0")),
]

MMC = r"%SystemRoot%\System32\mmc.exe /s %SystemRoot%\System32\{}"

CONTEXT = [
    Tweak("take_ownership", "context",
          menu_item(HKCU_CLASSES + r"\*\shell\SimpleTool.TakeOwnership", menu_label("take_ownership"),
                    elevated(rf'/c takeown /f \"%1\" /a & icacls \"%1\" /grant {ADMINS}:F /c', hidden=False),
                    icon="imageres.dll,-78", extended=True, shield=True)
          + menu_item(HKCU_CLASSES + r"\Directory\shell\SimpleTool.TakeOwnership", menu_label("take_ownership"),
                      elevated(rf'/c takeown /f \"%1\" /r /a & icacls \"%1\" /grant {ADMINS}:F /t /c /q', hidden=False),
                      icon="imageres.dll,-78", extended=True, shield=True)),
    Tweak("firewall", "context",
          menu_item(HKCU_CLASSES + r"\exefile\shell\SimpleTool.FirewallBlock", menu_label("firewall_block"),
                    elevated(rf'/c netsh advfirewall firewall add rule {FIREWALL_RULE} dir=out action=block program=\"%1\" '
                             rf'& netsh advfirewall firewall add rule {FIREWALL_RULE} dir=in action=block program=\"%1\"'),
                    icon="FirewallControlPanel.dll,0", extended=True, shield=True)
          + menu_item(HKCU_CLASSES + r"\exefile\shell\SimpleTool.FirewallAllow", menu_label("firewall_allow"),
                      elevated(rf"/c netsh advfirewall firewall delete rule {FIREWALL_RULE}"),
                      icon="FirewallControlPanel.dll,0", extended=True, shield=True)),
    Tweak("cmd_desktop", "context",
          menu_item(HKCU_CLASSES + r"\DesktopBackground\Shell\SimpleTool.Cmd", menu_label("cmd"),
                    'cmd.exe /s /k pushd "%V"', icon="cmd.exe")),
    Tweak("file_hash", "context",
          submenu(HKCU_CLASSES + r"\*\shell\SimpleTool.Hash", menu_label("hash"), "imageres.dll,-5360",
                  [(f"{i}{name}", menu_label("hash_copy", name), hash_command(name)) for i, name in enumerate(HASHES, 1)])),
    Tweak("copy_image", "context", [
        op for ext in IMAGE_TYPES
        for op in menu_item(rf"{HKCU_CLASSES}\SystemFileAssociations\{ext}\shell\SimpleTool.CopyImage",
                            menu_label("copy_image"), COPY_IMAGE_COMMAND, icon="shell32.dll,-16763")
    ]),
    Tweak("new_files", "context", [
        op for ext in (".cmd", ".reg")
        for op in (OwnedKey(rf"{HKLM_CLASSES}\{ext}\ShellNew"), Value(rf"{HKLM_CLASSES}\{ext}\ShellNew", "NullFile", "", REG_SZ))
    ]),
    Tweak("hidden_items", "context", [
        op for base in ("Directory", r"Directory\Background")
        for op in (
            OwnedKey(rf"{HKCU_CLASSES}\{base}\shell\SimpleTool.HiddenItems"),
            # Встроенная команда Проводника «Скрытые элементы»; подпись Windows переводит сама
            Value(rf"{HKCU_CLASSES}\{base}\shell\SimpleTool.HiddenItems", "ExplorerCommandHandler",
                  "{f7300245-1f4b-41ba-8948-6fd392064494}", REG_SZ),
            Value(rf"{HKCU_CLASSES}\{base}\shell\SimpleTool.HiddenItems", "CommandStateSync", "", REG_SZ),
            Value(rf"{HKCU_CLASSES}\{base}\shell\SimpleTool.HiddenItems", "MUIVerb", "@shell32.dll,-37572", REG_SZ),
            Value(rf"{HKCU_CLASSES}\{base}\shell\SimpleTool.HiddenItems", "Description", "@shell32.dll,-37573", REG_SZ),
            Value(rf"{HKCU_CLASSES}\{base}\shell\SimpleTool.HiddenItems", "Icon", "imageres.dll,-5314", REG_SZ),
        )
    ]),
    Tweak("notepad", "context", [
        OwnedKey(HKCU_CLASSES + r"\Unknown\shell\edit"),
        Value(HKCU_CLASSES + r"\Unknown\shell\edit\command", "", r'"%SystemRoot%\System32\notepad.exe" "%1"', REG_EXPAND_SZ),
        OwnedKey(HKCU_CLASSES + r"\MSInfoFile\shell\open"),
        Value(HKCU_CLASSES + r"\MSInfoFile\shell\open\command", "", r'"%SystemRoot%\System32\notepad.exe" "%1"', REG_EXPAND_SZ),
    ]),
    Tweak("this_pc_tools", "context",
          menu_item(THIS_PC + r"\SimpleTool.1ControlPanel", menu_label("control_panel"), "control.exe", icon="control.exe")
          + menu_item(THIS_PC + r"\SimpleTool.2DeviceManager", menu_label("device_manager"),
                      MMC.format("devmgmt.msc"), icon="devmgr.dll,4", kind=REG_EXPAND_SZ)
          + menu_item(THIS_PC + r"\SimpleTool.3Services", menu_label("services"),
                      MMC.format("services.msc"), icon="filemgmt.dll,0", kind=REG_EXPAND_SZ)
          + menu_item(THIS_PC + r"\SimpleTool.4DiskManagement", menu_label("disk_management"),
                      MMC.format("diskmgmt.msc"), icon="dmdskres.dll,0", shield=True, kind=REG_EXPAND_SZ)
          + menu_item(THIS_PC + r"\SimpleTool.5Registry", menu_label("registry_editor"), "regedit.exe",
                      icon="regedit.exe", shield=True)
          + menu_item(THIS_PC + r"\SimpleTool.6Programs", menu_label("programs"), "control.exe appwiz.cpl",
                      icon="appwiz.cpl,4")
          + submenu(THIS_PC + r"\SimpleTool.7SafeMode", menu_label("safe_mode"), "msconfig.exe", SAFE_MODE)),
]

TWEAKS = PRIVACY + SYSTEM + EXPLORER_TWEAKS + CONTEXT
