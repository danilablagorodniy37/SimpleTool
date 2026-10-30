"""Troubleshooting: looks for common causes of slowdowns, crashes and conflicts on this PC.

Everything here only reads: memory and processor counters, drives, the registry, the hosts file, the Windows event
logs and a few system lists through PowerShell. Nothing is changed and nothing leaves the PC.

gather() collects facts, evaluate() turns them into findings. They are separate so the tests can check every
verdict on made-up facts. A fact that could not be read is missing, and its check says so instead of guessing.
"""
import ctypes
import datetime
import glob
import json
import os
import re
import struct
import subprocess
import threading
import time
import uuid
import winreg
import xml.etree.ElementTree as ElementTree
from ctypes import wintypes

import engine
import limiter
import programs
import services
import sysinfo

GROUPS = ["performance", "storage", "stability", "security"]
# (check, group) in the order they are shown
CHECKS = [
    ("ram_load", "performance"), ("ram_size", "performance"), ("memory_config", "performance"),
    ("kernel_memory", "performance"), ("pagefile", "performance"), ("cpu_load", "performance"),
    ("cpu_microcode", "performance"), ("x3d_cores", "performance"), ("power_plan", "performance"),
    ("graphics_driver", "performance"), ("display_output", "performance"), ("gpu_link", "performance"),
    ("gpu_preference", "performance"), ("refresh_rate", "performance"), ("video_memory", "performance"),
    ("startup_apps", "performance"), ("boot_time", "performance"),
    ("rgb_software", "performance"), ("conflicting_software", "performance"), ("game_dvr", "performance"),
    ("xbox_network", "performance"), ("boot_options", "performance"),
    ("throttling", "performance"), ("uptime", "performance"),
    ("disk_space", "storage"), ("disk_health", "storage"), ("system_drive", "storage"), ("drive_link", "storage"),
    ("disk_errors", "storage"), ("volume_health", "storage"), ("temp_files", "storage"),
    ("crashes", "stability"), ("app_crashes", "stability"), ("crash_files", "stability"), ("gpu_resets", "stability"),
    ("live_kernel", "stability"), ("whea", "stability"),
    ("memory_test", "stability"), ("devices", "stability"), ("services", "stability"),
    ("core_services", "stability"), ("app_platform", "stability"), ("system_files", "stability"),
    ("recovery_env", "stability"), ("wmi_health", "stability"), ("time_sync", "stability"), ("vc_runtime", "stability"),
    ("media_pack", "stability"), ("battery", "stability"),
    ("antivirus", "security"), ("defender", "security"), ("security_settings", "security"),
    ("blocked_tools", "security"), ("memory_integrity", "security"),
    ("secure_boot", "security"), ("windows_update", "security"), ("pending_restart", "security"),
    ("windows_support", "security"), ("network", "security"), ("network_exposure", "security"),
    ("proxy", "security"), ("hosts", "security"), ("browser_policies", "security"), ("root_certificates", "security"),
    ("accounts", "security"), ("remote_tools", "security"), ("bitlocker", "security"),
]
GROUP_OF = dict(CHECKS)
SEVERITIES = ["problem", "warning", "info", "ok", "unknown"]  # from the most serious

# What each suggested action opens: a page of SimpleTool, or a program, folder or settings address with arguments
ACTIONS = {
    "memory": ("page", "memory", None),
    "system_config": ("open", "msconfig.exe", None),
    "taskmgr": ("open", "taskmgr.exe", None),
    "virtual_memory": ("open", "SystemPropertiesPerformance.exe", None),
    "power": ("open", "powercfg.cpl", None),
    "power_mode": ("open", "ms-settings:powersleep", None),
    "display": ("open", "ms-settings:display-advanced", None),
    "graphics_settings": ("open", "ms-settings:display-advancedgraphics", None),
    "startup": ("open", "ms-settings:startupapps", None),
    "captures": ("open", "ms-settings:gaming-gamedvr", None),
    "storage": ("open", "ms-settings:storagesense", None),
    "temp": ("open", "%TEMP%", None),
    "events": ("open", "eventvwr.msc", None),
    "reliability": ("open", "perfmon.exe", "/rel"),
    "devices": ("open", "devmgmt.msc", None),
    "services": ("open", "services.msc", None),
    "core_isolation": ("open", "windowsdefender://coreisolation", None),
    "security": ("open", "windowsdefender:", None),
    "update": ("open", "ms-settings:windowsupdate", None),
    "optional_features": ("open", "ms-settings:optionalfeatures", None),
    "uac": ("open", "UserAccountControlSettings.exe", None),
    "recovery": ("open", "ms-settings:recovery", None),
    "apps": ("open", "ms-settings:appsfeatures", None),
    "system_properties": ("open", "SystemPropertiesAdvanced.exe", None),
    "network_status": ("open", "ms-settings:network-status", None),
    "proxy": ("open", "ms-settings:network-proxy", None),
    "hosts": ("open", "notepad.exe", "%HOSTS%"),
    "date_time": ("open", "ms-settings:dateandtime", None),
    "accounts": ("open", "ms-settings:otherusers", None),
    "firewall": ("open", "windowsdefender://network", None),
    "encryption": ("open", "ms-settings:deviceencryption", None),
}

EVENT_DAYS = 30      # crashes, drive and hardware errors are looked for this far back
APP_EVENT_DAYS = 14  # program crashes: a program that crashed a month ago has likely been updated since
SERVICE_DAYS = 7     # services that fail now: an old failure may have been fixed by an update
SERVICE_FAILURES = 5  # a service failing this often in a week keeps failing; once or twice happens on healthy PCs
UPDATE_FAILURES = 2  # a Windows update failing once is retried by itself; failing again it is stuck
THROTTLE_DAYS = 7
THROTTLE_SECONDS = 3600  # a desktop slowed down by its firmware for an hour in a week is held back for real
CPU_SAMPLE = 1.0     # seconds the processor load is measured over
TEMP_BUDGET = 3.0    # seconds to add up the temporary folder: a huge one is reported as "at least"
TEMP_MANY_FILES = 20_000  # this many files in the temporary folder slow down every program that lists it
TEMP_TOP_MIN = 300 * 1024 ** 2  # an entry of the temporary folder big enough to name
TEMP_FAMILY_MIN = 1000    # loose files with the same name pattern: one program littering
CBS_LOG_LIMIT = 1024 ** 3  # a servicing log this big is the known fault that fills the disk with cab_* files
CRASH_FILE_DAYS = 14      # crash reports programs keep themselves: the same window as the Windows log
LIVE_KERNEL_DAYS = 60     # live kernel dumps: rarer than program crashes, so a longer window
PERF_DAYS = 60            # what slowed the starts: Windows keeps about two months in its small log
SLOW_START_MS = 1000      # a driver, service or device that delays the start this much in several starts
SLOW_START_TOTAL_MS = 5000
SLOW_STARTS = 2           # in this many starts of the window: once can be a one-off (an update, a new device)
VIDEO_MEMORY_EVENTS = 3   # times the desktop ran out of video memory in EVENT_DAYS before it is worth saying
STARTUP_HIGH_MS, STARTUP_HIGH_DISK = 1000, 3 * 1024 ** 2  # Task Manager's "High" startup impact
INTERRUPTS_HIGH, INTERRUPTS_NOW_HIGH = 5.0, 25.0  # % of one processor: since the start, during the sample
NVME_WORN, NVME_WORN_OUT = 90, 100  # % of the rated endurance used (CrystalDiskInfo: Caution at 10% left)
# Programs that catch their own crashes and keep the reports in files (Crashpad, Unreal Engine, Breakpad):
# (program, pattern). * stands for any name in that segment; a pattern ending in \* counts entries, one per crash.
# %STEAM% is Steam's install folder. These crashes never reach the Windows log
CRASH_LOCATIONS = [
    ("Google Chrome", r"%LocalAppData%\Google\Chrome\User Data\Crashpad\reports\*.dmp"),
    ("Chromium", r"%LocalAppData%\Chromium\User Data\Crashpad\reports\*.dmp"),
    ("Microsoft Edge", r"%LocalAppData%\Microsoft\Edge\User Data\Crashpad\reports\*.dmp"),
    ("Brave", r"%LocalAppData%\BraveSoftware\Brave-Browser\User Data\Crashpad\reports\*.dmp"),
    ("Vivaldi", r"%LocalAppData%\Vivaldi\User Data\Crashpad\reports\*.dmp"),
    ("Opera", r"%AppData%\Opera Software\Opera Stable\Crashpad\reports\*.dmp"),
    ("Opera GX", r"%AppData%\Opera Software\Opera GX Stable\Crashpad\reports\*.dmp"),
    ("Yandex Browser", r"%LocalAppData%\Yandex\YandexBrowser\User Data\Crashpad\reports\*.dmp"),
    ("Discord", r"%AppData%\discord\Crashpad\reports\*.dmp"),
    ("Discord PTB", r"%AppData%\discordptb\Crashpad\reports\*.dmp"),
    ("Discord Canary", r"%AppData%\discordcanary\Crashpad\reports\*.dmp"),
    ("Visual Studio Code", r"%AppData%\Code\Crashpad\reports\*.dmp"),
    ("Microsoft Teams", r"%AppData%\Microsoft\Teams\Crashpad\reports\*.dmp"),
    ("Slack", r"%AppData%\Slack\Crashpad\reports\*.dmp"),
    ("Signal", r"%AppData%\Signal\Crashpad\reports\*.dmp"),
    ("WhatsApp", r"%AppData%\WhatsApp\Crashpad\reports\*.dmp"),
    ("Obsidian", r"%AppData%\obsidian\Crashpad\reports\*.dmp"),
    ("Logitech G HUB", r"%AppData%\G HUB\Crashpad\reports\*.dmp"),
    ("Steam", r"%STEAM%\dumps\*.dmp"),
    ("Steam", r"%STEAM%\dumps\reports\*.dmp"),
    ("Epic Games Launcher", r"%LocalAppData%\EpicGamesLauncher\Saved\Crashes\*"),
    ("Riot Client", r"%LocalAppData%\Riot Games\Riot Client\Crashes\*\reports\*.dmp"),
    ("VALORANT", r"%LocalAppData%\VALORANT\Saved\Crashes\*"),
    ("GOG Galaxy", r"%ProgramData%\GOG.com\Galaxy\crashdumps\*.dmp"),
    ("Telegram Desktop", r"%AppData%\Telegram Desktop\tdata\dumps\*.dmp"),
    ("OBS Studio", r"%AppData%\obs-studio\crashes\*"),
    ("NVIDIA", r"%ProgramData%\NVIDIA Corporation\CrashDumps\*"),
    ("Mozilla Firefox", r"%AppData%\Mozilla\Firefox\Profiles\*\minidumps\*.dmp"),
    ("Thunderbird", r"%AppData%\Thunderbird\Profiles\*\minidumps\*.dmp"),
]
# Windows Error Reporting keeps a folder per report; its name starts with the kind and the program
WER_QUEUES = [r"%ProgramData%\Microsoft\Windows\WER\ReportQueue", r"%ProgramData%\Microsoft\Windows\WER\ReportArchive",
              r"%LocalAppData%\Microsoft\Windows\WER\ReportQueue", r"%LocalAppData%\Microsoft\Windows\WER\ReportArchive"]
WER_KINDS = ("AppCrash", "AppHang", "Critical", "NonCritical")
# Where Windows Error Reporting writes its local dumps (the LocalDumps key), for the user and for services
LOCAL_DUMPS_KEY = r"HKLM\SOFTWARE\Microsoft\Windows\Windows Error Reporting\LocalDumps"
LOCAL_DUMP_FOLDERS = [r"%LocalAppData%\CrashDumps",
                      r"%SystemRoot%\System32\config\systemprofile\AppData\Local\CrashDumps",
                      r"%SystemRoot%\ServiceProfiles\LocalService\AppData\Local\CrashDumps",
                      r"%SystemRoot%\ServiceProfiles\NetworkService\AppData\Local\CrashDumps"]
CRASH_CONTROL = r"HKLM\SYSTEM\CurrentControlSet\Control\CrashControl"
# The folders of C:\Windows\LiveKernelReports, by the component that stopped responding
LIVE_KERNEL_KINDS = {"watchdog": "kind_live_watchdog", "ndis": "kind_live_ndis", "usbhub3": "kind_live_usb",
                     "usbxhci": "kind_live_usb", "usbhub": "kind_live_usb", "pow32kwatchdog": "kind_live_power",
                     "pdcrevocation": "kind_live_power", "pdc": "kind_live_power"}
LIVE_KERNEL_HINTS = {"kind_live_watchdog": "item_live_watchdog_hint", "kind_live_ndis": "item_live_ndis_hint",
                     "kind_live_usb": "item_live_usb_hint", "kind_live_power": "item_live_power_hint"}
# Programs and drivers with documented problems: the services, Store packages and files to look at
WATCHED_SERVICES = re.compile(r"nahimic|a-volute|killer|rivet|cfosspeed|inpoutx64|armourycrate", re.IGNORECASE)
WATCHED_PACKAGES = re.compile(r"nahimic|a-volute|sonicstudio|sonicradar", re.IGNORECASE)
RTSS_PATH = r"%ProgramFiles(x86)%\RivaTuner Statistics Server\RTSS.exe"
RTSS_FIXED = (7, 3, 7)  # Overwolf: older RivaTuner versions cause low FPS, mouse lag and freezes next to it
LGS_FIXED = (8, 98)     # Logitech: Gaming Software and G HUB live together only from this version
PUP_PROGRAMS = ("advanced systemcare", "driverpack")  # classified as potentially unwanted by antivirus makers
SCAM_PROGRAMS = ("restoro", "reimage")                 # fined by the US FTC in 2024 for fake Windows warnings
OPTIMIZER_PROGRAMS = ("driver booster", "driver easy", "wise care", "avast cleanup", "avg tuneup", "avg pc tuneup",
                      "smart game booster")
POWERSHELL_TIMEOUT = 120
GB = 1024 ** 3
MB = 1024 ** 2

# Power plans that come with Windows
POWER_SAVER = "a1841308-3541-4fab-bc81-f71556f20b4a"
# The Windows 11 power mode (Settings > Power) on top of the plan
OVERLAY_EFFICIENCY = "961cc777-2547-4f9d-8174-7d86181b8a7a"
# Processor power management, the values while plugged in: maximum processor state (all cores and the efficient
# cores of a hybrid processor), turbo boost, and frequency caps in MHz (0 means no cap)
PROCESSOR_SUBGROUP = "54533251-82be-4824-96c1-47b60b740d00"
PROCESSOR_SETTINGS = {"max_cpu": "bc5038f7-23e0-4960-96da-33abaf5935ec", "max_cpu1": "bc5038f7-23e0-4960-96da-33abaf5935ed",
                      "boost": "be337238-0d82-4146-a960-4f3749d470c7", "max_mhz": "75b0ae3f-bce0-45a7-8c89-c9611c25e100",
                      "max_mhz1": "75b0ae3f-bce0-45a7-8c89-c9611c25e101",
                      # 1: the processor never rests (Atlas OS and similar "Disable Idle")
                      "idle_disable": "5d76a2ca-e8c0-402f-a133-2158492d58ad"}

# Boot options that limit or debug Windows (bcdedit, msconfig → Boot → Advanced options), as SystemStartOptions
# lists them
BOOT_PROCESSORS = ("NUMPROC", "ONECPU")
BOOT_MEMORY = ("MAXMEM", "TRUNCATEMEMORY", "REMOVEMEMORY", "BURNMEMORY")
HPET_FREQUENCY = 14318180  # QueryPerformanceFrequency when "useplatformclock" forces the HPET timer
# CodeIntegrityOptions (NtQuerySystemInformation, SystemCodeIntegrityInformation)
CI_ENABLED, CI_TESTSIGN, CI_DEBUG, CI_HVCI = 0x1, 0x2, 0x80, 0x400
MBEC = 7  # Win32_DeviceGuard.AvailableSecurityProperties: the processor has what memory integrity needs to be fast

# Windows builds and when their security updates end: (version, Home and Pro, Enterprise and Education).
# Windows 10 ended for every edition; Extended Security Updates are paid separately and cannot be seen from here
SUPPORT_ENDS = {
    19045: ("22H2", datetime.date(2025, 10, 14), datetime.date(2025, 10, 14)),
    22000: ("21H2", datetime.date(2023, 10, 10), datetime.date(2024, 10, 8)),
    22621: ("22H2", datetime.date(2024, 10, 8), datetime.date(2025, 10, 14)),
    22631: ("23H2", datetime.date(2025, 11, 11), datetime.date(2026, 11, 10)),
    26100: ("24H2", datetime.date(2026, 10, 13), datetime.date(2027, 10, 12)),
    26200: ("25H2", datetime.date(2027, 10, 12), datetime.date(2028, 10, 10)),
    26300: ("26H2", datetime.date(2028, 10, 10), datetime.date(2029, 10, 9)),
    28000: ("26H1", datetime.date(2028, 3, 14), datetime.date(2029, 3, 13)),
}
SUPPORT_WARN_DAYS = 60
LONG_EDITIONS = ("Enterprise", "Education", "IoTEnterprise")  # 36 months instead of 24 (by EditionID prefix)

# Addresses Windows needs: blocked in the hosts file, they break Windows Update, the Store, activation, sign-in,
# Xbox, Defender updates, the clock or the "connected to the internet" check. Blocking telemetry is fine
NEEDED_DOMAINS = ("windowsupdate.com", "update.microsoft.com", "delivery.mp.microsoft.com",
                  "displaycatalog.mp.microsoft.com", "storeedgefd.dsx.mp.microsoft.com", "licensing.mp.microsoft.com",
                  "sls.microsoft.com", "login.live.com", "login.microsoftonline.com", "xboxlive.com",
                  "definitionupdates.microsoft.com", "msftconnecttest.com", "msftncsi.com", "time.windows.com")
HOSTS_MANY = 20000  # a hosts file this long slows down every name lookup

# Graphics makers by PCI vendor ID. NVIDIA makes only graphics cards; AMD and Intel also make the graphics built
# into processors, told apart by the name: "Radeon RX 7800 XT", "Arc A770" and "Arc B580" are cards,
# "Radeon RX Vega 11 Graphics", "UHD Graphics", "Arc Graphics" and "Arc B390" are inside the processor. The memory a
# driver reports does not tell: Intel's processor graphics report 2 GB of their own
NVIDIA, AMD, INTEL = "10DE", "1002", "8086"
DISCRETE_NAMES = re.compile(r"\bRX \d|\bRX Vega (56|64)\b|Radeon Pro|Radeon VII|FirePro|"
                            r"\bArc(\(TM\))? (A\d{3}|B[5-9]\d\d)M?\b", re.IGNORECASE)
OLD_DRIVER_DAYS = 548  # a year and a half: the makers release new drivers every month or two
# NVIDIA drivers before 581.94 lose up to half the FPS in some games after the October 2025 Windows update
NVIDIA_FIXED = 581.94
NVIDIA_SLOW_FROM = 6899  # the update revision of that Windows update on builds 26100 and 26200
VIRTUAL_MACHINES = re.compile(r"virtual machine|vmware|virtualbox|qemu|kvm|parallels|xen", re.IGNORECASE)

# Intel 13th and 14th Gen desktop processors of the Raptor Lake die (model 183) degrade with old microcode
# ("Vmin shift"); 0x12B fixed the cause in September 2024, 0x12F is newer still
RAPTOR_NAME = re.compile(r"1[34]th Gen Intel\(R\) Core\(TM\) i[579]-1[34]\d{3}(K|KF|KS|F)?\b")
RAPTOR_MODEL = 183
RAPTOR_FIXED, RAPTOR_LATEST = 0x12B, 0x12F
# Ryzen 9 X3D processors have two core dies, one with the extra cache: games go there through AMD's driver and
# the Xbox Game Bar
X3D_DUAL = re.compile(r"Ryzen 9 \d{4}X3D", re.IGNORECASE)

# Memory modules: the rated speed some makers write into the part number, when the speed Windows reports is lower
RATED_SPEED = [
    (re.compile(r"^F[45]-(\d{4})"), lambda m: int(m.group(1))),  # G.Skill: F4-3600C16D-16GTZN, F5-6000J3038F16G
    (re.compile(r"X[45]M\d[A-Z](\d{4})C\d"), lambda m: int(m.group(1))),  # Corsair: CMK16GX4M2B3200C16
    (re.compile(r"^KF[45](\d\d)C"), lambda m: 2666 if m.group(1) == "26" else int(m.group(1)) * 100),  # Kingston
    (re.compile(r"^BL\d+G(\d\d)C"), lambda m: int(m.group(1)) * 100),  # Crucial Ballistix: BL8G36C16U4B
    (re.compile(r"(\d{4})HC\d"), lambda m: int(m.group(1))),  # TeamGroup: TF3D416G3600HC18J
]
DIMM, SODIMM = 8, 12  # Win32_PhysicalMemory.FormFactor

# Device Manager problem codes with their own explanation; others show the number
DEVICE_CODES = (1, 3, 10, 12, 14, 18, 19, 21, 24, 28, 31, 32, 37, 39, 41, 43, 48, 52)
DEVICE_IGNORED = (22, 45)  # disabled by the user, not connected right now

# System log events (provider, id) -> kind of drive error
DISK_EVENTS = {("disk", 7): "bad_block", ("disk", 11): "controller", ("disk", 51): "paging", ("disk", 153): "retry",
               ("ntfs", 55): "ntfs", ("ntfs", 50): "write",
               ("ntfs", 98): "repair"}  # a warning or an error: the volume needs an offline check (chkdsk)
DISK_SERIOUS = ("bad_block", "controller", "paging", "ntfs", "write", "repair")
DISK_PROVIDERS = ("disk", "Ntfs", "Microsoft-Windows-Ntfs", "storahci", "stornvme", "iaStorA", "iaStorAC", "iaStorAV",
                  "iaStorAVC", "storport")
STORAGE_RESET_PROVIDERS = ("storahci", "stornvme", "iastora", "iastorac", "iastorav", "iastoravc", "storport")
REMOVABLE_BUSES = ("USB", "SD", "MMC")  # memory sticks and cards: errors when they are pulled out are normal
NVIDIA_RESET, NVIDIA_EXCEPTIONS = 153, (13, 14)  # nvlddmkm: the driver restarted; graphics exceptions
GPU_HANGS = ("117", "141")  # live kernel events: VIDEO_TDR_TIMEOUT_DETECTED, VIDEO_ENGINE_TIMEOUT_DETECTED
# WHEA-Logger: fatal errors, corrected errors in the processor and the memory (a sign of instability), PCIe
WHEA_FATAL, WHEA_UNSTABLE, WHEA_PCIE = (1, 18, 46), (19, 47), 17
WHEA_PCIE_STORM = 100  # corrected PCIe errors per day that point to a bad slot, riser or power saving

# Program crashes: the module a crash happened in tells who is to blame
OVERLAY_MODULES = {"rtsshooks64.dll": "RivaTuner Statistics Server", "rtsshooks.dll": "RivaTuner Statistics Server",
                   "gameoverlayrenderer64.dll": "Steam", "gameoverlayrenderer.dll": "Steam",
                   "discordhook64.dll": "Discord", "discordhook.dll": "Discord", "graphics-hook64.dll": "OBS Studio",
                   "graphics-hook32.dll": "OBS Studio", "igo64.dll": "EA app", "igo32.dll": "EA app",
                   "nahimicosd.dll": "Nahimic", "nahimicmsiosd.dll": "Nahimic"}
OVERLAY_PREFIXES = {"ow-graphics-": "Overwolf"}
GPU_MODULES = ("nvwgf2um", "nvoglv", "nvd3dum", "nvldumd", "amdxx", "atidxx", "atiumd", "amdvlk", "atio6axx",
               "igd10iumd", "igd12um", "igxelpicd", "igd1xumd", "igdumd", "igc64")
CRASH_SYSTEM_MODULES = ("ntdll.dll", "kernelbase.dll")
CRASH_ACCESS, CRASH_IN_PAGE, CRASH_ILLEGAL = "c0000005", "c0000006", "c000001d"
UNSTABLE_PROGRAMS = 4  # this many unrelated programs failing the same way inside Windows' own code

# Programs that drive the lighting of the motherboard and memory: two at once fight over the same chips
RGB_PROGRAMS = {"armourycrate": "Armoury Crate", "armourycrate.service": "Armoury Crate", "lightingservice": "ASUS Aura",
                "icue": "Corsair iCUE", "corsair.service": "Corsair iCUE", "signalrgb": "SignalRGB",
                "openrgb": "OpenRGB", "msi.centralserver": "MSI Center", "msi center": "MSI Center",
                "rgbfusion": "RGB Fusion", "gcc": "Gigabyte Control Center", "nzxt cam": "NZXT CAM",
                "razerappengine": "Razer Synapse", "razer synapse 3": "Razer Synapse"}

# Services that "debloat" tools turn off. Disabled, they break what they are for: (service, effect)
CORE_SERVICES = [("BITS", "updates"), ("UsoSvc", "updates"), ("TrustedInstaller", "updates"), ("CryptSvc", "updates"),
                 # Delivery Optimization downloads updates and Store apps (0x80004002 without it); the medic service
                 # repairs Windows Update
                 ("DoSvc", "updates"), ("WaaSMedicSvc", "updates"),
                 ("msiserver", "install"), ("AppXSvc", "install"), ("ClipSVC", "install"), ("InstallService", "install"),
                 ("Audiosrv", "sound"), ("AudioEndpointBuilder", "sound"), ("BFE", "firewall"), ("mpssvc", "firewall"),
                 ("wscsvc", "security"),
                 ("EventLog", "logs"), ("Winmgmt", "logs"), ("Schedule", "tasks"), ("Dhcp", "network"),
                 ("Dnscache", "network"), ("W32Time", "clock")]
# Disabled, these only take a feature away: noted, not a problem
OPTIONAL_SERVICES = [("XblAuthManager", "xbox"), ("XboxGipSvc", "xbox"), ("GamingServices", "xbox"),
                     ("iphlpsvc", "xbox"), ("WSearch", "search"), ("WerSvc", "reports"), ("DPS", "diagnostics")]
SMALL_MEMORY = 8 * GB  # with this much RAM or less SysMain also runs memory compression

VC_RUNTIME_MIN = (14, 40)  # programs built with Visual Studio 2022 17.10 crash at start on an older runtime
ANTI_CHEAT_TPM = ("vgk", "vgc")  # Riot Vanguard: refuses to start on Windows 11 without TPM 2.0 and Secure Boot
# Windows Update: Microsoft Store apps appear as "9WZDNCRFJBMP-Microsoft.WindowsStore"; 0x80073D02 means the app
# was running at the time, and the Store tries again later. Defender's definitions update every few hours
STORE_APP = re.compile(r"^[0-9A-Z]{12}-")
UPDATE_ERRORS_IGNORED = ("0x80073D02",)
UPDATE_FAMILIES_IGNORED = ("security intelligence update",)
PER_USER_SERVICE = re.compile(r"_[0-9a-f]{4,}$", re.IGNORECASE)  # "Clipboard User Service_4a3b1"
SERVICES_IGNORED = ("luafv",)  # fails at every start when UAC is off: that is reported by itself
SHUTDOWN_GRACE = datetime.timedelta(minutes=2)  # services that stop badly while Windows shuts down

# Image File Execution Options: a "Debugger" value starts another program instead of this one. Tweaking tools block
# programs with it (often with systray.exe, which starts and quits at once), malware blocks protection with it, and a
# debugger on a program of the sign-in screen opens a command prompt there (MITRE ATT&CK T1546.012, T1546.008)
IFEO = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Image File Execution Options"
PROTECTION_PROGRAMS = {
    "msmpeng.exe", "mpcmdrun.exe", "nissrv.exe", "mpdefendercoreservice.exe", "securityhealthservice.exe",
    "securityhealthsystray.exe", "securityhealthhost.exe", "smartscreen.exe", "mrt.exe", "wuauclt.exe",
    "usoclient.exe", "mousocoreworker.exe", "taskmgr.exe", "regedit.exe", "mmc.exe", "msconfig.exe", "rstrui.exe",
    "cmd.exe", "powershell.exe", "autoruns.exe", "autoruns64.exe", "procexp.exe", "procexp64.exe", "frst.exe",
    "frst64.exe", "adwcleaner.exe", "mbam.exe", "mbamtray.exe", "mbamservice.exe", "malwarebytes.exe", "avp.exe",
    "avpui.exe", "ekrn.exe", "egui.exe", "avastui.exe", "avastsvc.exe", "avgui.exe", "avgsvc.exe", "bdagent.exe",
    "vsserv.exe", "mcshield.exe", "hitmanpro.exe", "hitmanpro_x64.exe", "tdsskiller.exe", "kvrt.exe", "zam.exe",
    "sophosui.exe", "esetonlinescanner.exe", "cureit.exe"}
SIGN_IN_PROGRAMS = {"sethc.exe", "utilman.exe", "osk.exe", "magnify.exe", "narrator.exe", "displayswitch.exe",
                    "atbroker.exe"}
# Programs that offer to replace a Windows tool through the same value, and debuggers developers use on purpose
DEBUGGER_REPLACEMENTS = {"taskmgr.exe": re.compile(r"procexp|systeminformer|processhacker", re.IGNORECASE),
                         "regedit.exe": re.compile(r"regworkshop|regcool", re.IGNORECASE)}
DEVELOPER_DEBUGGERS = re.compile(r"vsjitdebugger|windbg|\bcdb\.exe|\bntsd\.exe|devenv|x64dbg|x32dbg|ollydbg",
                                 re.IGNORECASE)
USER_FOLDERS = re.compile(r"\\appdata\\|\\temp\\|\\users\\public\\|\\programdata\\", re.IGNORECASE)
# Policies that lock Windows tools: (key under Software, value, values that lock, what it locks). Schools and
# workplaces set some on purpose; malware sets them so the user cannot look for it
TOOL_LOCKS = [(r"Microsoft\Windows\CurrentVersion\Policies\System", "DisableTaskMgr", (1,), "taskmgr"),
              (r"Microsoft\Windows\CurrentVersion\Policies\System", "DisableRegistryTools", (1, 2), "regedit"),
              (r"Policies\Microsoft\Windows\System", "DisableCMD", (1, 2), "cmd"),
              (r"Microsoft\Windows\CurrentVersion\Policies\Explorer", "NoRun", (1,), "run"),
              (r"Microsoft\Windows\CurrentVersion\Policies\Explorer", "NoControlPanel", (1,), "control_panel"),
              (r"Microsoft\Windows\CurrentVersion\Policies\Explorer", "NoFolderOptions", (1,), "folder_options"),
              (r"Microsoft\Windows\CurrentVersion\Policies\Explorer", "DisallowRun", (1,), "disallow_run"),
              (r"Microsoft\Windows\CurrentVersion\Policies\Explorer", "RestrictRun", (1,), "restrict_run")]
# Security software, by the names in its folders and certificates: malware blocks it in the firewall or marks its
# certificates as untrusted so it cannot start or update (FRST reports both)
SECURITY_VENDORS = re.compile(
    r"windows defender|\bmsmpeng|\bmpcmdrun|malwarebytes|kaspersky|\beset\b|avast|\bavg\b|avira|bitdefender|"
    r"norton|symantec|mcafee|sophos|trend ?micro|emsisoft|dr\.?web|doctor web|f-secure|withsecure|g data|"
    r"panda security|webroot|comodo|hitmanpro|adwcleaner|\bqihoo|zillya|quick heal|ahnlab|vipre", re.IGNORECASE)
FIREWALL_RULES = r"SYSTEM\CurrentControlSet\Services\SharedAccess\Parameters\FirewallPolicy\FirewallRules"
# Microsoft Defender settings set by a policy that turn its protection off. Tamper protection ignores them on a PC
# that is not managed by an organization, so they only work where it is off
DEFENDER_POLICY = r"HKLM\SOFTWARE\Policies\Microsoft\Windows Defender"
DEFENDER_POLICIES = [(DEFENDER_POLICY, "DisableAntiSpyware"), (DEFENDER_POLICY, "DisableAntiVirus"),
                     (DEFENDER_POLICY + r"\Real-Time Protection", "DisableRealtimeMonitoring"),
                     (DEFENDER_POLICY + r"\Real-Time Protection", "DisableBehaviorMonitoring"),
                     (DEFENDER_POLICY + r"\Real-Time Protection", "DisableOnAccessProtection"),
                     (DEFENDER_POLICY + r"\Real-Time Protection", "DisableIOAVProtection")]
# Settings pages a policy can hide (SettingsPageVisibility "hide:a;b" or "showonly:a;b")
HIDDEN_PAGES = ("windowsdefender", "windowsupdate")
WU_POLICY = r"HKLM\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate"
LOCAL_SERVERS = re.compile(r"^(https?://)?(localhost|127\.|0\.0\.0\.0|\[?::1\]?)", re.IGNORECASE)
PAUSE_LIMIT_DAYS = 35  # Settings lets updates be paused for five weeks; a later date was set around it
# Store packages Windows relies on: (package name prefix, what is lost without it). The per-user list of packages
# is the one Windows itself keeps in the registry
STORE_PACKAGE = "microsoft.windowsstore_"
SECURITY_APP_PACKAGES = ("microsoft.sechealthui_", "microsoft.windows.sechealthui_")
SHELL_PACKAGE = "microsoftwindows.client.cbs_"  # Windows 11: parts of Start, the taskbar, search and Settings
APP_INSTALLER_PACKAGE = "microsoft.desktopappinstaller_"  # winget and .msix installers
XBOX_IDENTITY_PACKAGE = "microsoft.xboxidentityprovider_"  # signs PC Game Pass games in to Xbox
GAMING_PACKAGES = ("microsoft.gamingapp_", "microsoft.gamingservices_")
WEBVIEW2 = "{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"  # the Evergreen WebView2 runtime, as EdgeUpdate registers it
WEBVIEW2_KEYS = [rf"HKLM\SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{WEBVIEW2}",
                 rf"HKLM\SOFTWARE\Microsoft\EdgeUpdate\Clients\{WEBVIEW2}",
                 rf"HKCU\Software\Microsoft\EdgeUpdate\Clients\{WEBVIEW2}"]
NO_STORE_EDITIONS = ("EnterpriseS", "IoTEnterpriseS", "ServerRdsh")  # LTSC: no Store by design
DEPROVISIONED = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Appx\AppxAllUserStore\Deprovisioned"
# Power: the policy "Allow standby states (S1-S3) when sleeping"
STANDBY_POLICY = r"HKLM\SOFTWARE\Policies\Microsoft\Power\PowerSettings\abfc2519-3608-4c2a-94ea-171b0ed546ab"
# Networking games need: Teredo (MSFT_NetTeredoConfiguration.Type 4 is Disabled), the IP Helper service and IPv6.
# DisabledComponents 0xFFFFFFFF delays every start by 5 seconds; Microsoft recommends 0xFF to turn IPv6 off
TEREDO_DISABLED = 4
IPV6_DELAY = 0xFFFFFFFF
IPV6_TUNNELS_OFF = 0x01 | 0x08  # tunnel interfaces, Teredo
SVCHOST_SPLIT, SVCHOST_DEFAULT = "SvcHostSplitThresholdInKB", 3670016
# Microsoft Defender exclusions Microsoft names as mistakes: whole drives and the system, user and temporary
# folders, every file of a common type, and the programs that run scripts and system code
BROAD_FOLDERS = ("%SystemRoot%", r"%SystemRoot%\System32", r"%SystemRoot%\Temp", "%ProgramFiles%",
                 "%ProgramFiles(x86)%", "%ProgramData%", r"%SystemDrive%\Users", "%USERPROFILE%", "%APPDATA%",
                 "%LOCALAPPDATA%", "%TEMP%", r"%USERPROFILE%\Downloads", r"%USERPROFILE%\Desktop")
BROAD_EXTENSIONS = {"exe", "dll", "sys", "ps1", "bat", "cmd", "com", "js", "jse", "vbs", "vbe", "wsf", "hta", "scr",
                    "msi", "jar", "lnk", "zip", "rar", "7z", "iso"}
BROAD_PROCESSES = {"powershell.exe", "pwsh.exe", "cmd.exe", "wscript.exe", "cscript.exe", "mshta.exe", "rundll32.exe",
                   "regsvr32.exe", "svchost.exe", "explorer.exe", "msiexec.exe", "schtasks.exe"}
# Threats Defender reports about settings the user may have changed on purpose: the hosts file has its own check
HOSTS_THREAT = re.compile(r"HostsFileHijack", re.IGNORECASE)
# Browsers' policy keys under HKLM and HKCU: forced extensions, start page, search engine and proxy
BROWSER_POLICY_KEYS = [("Google Chrome", r"SOFTWARE\Policies\Google\Chrome"),
                       ("Microsoft Edge", r"SOFTWARE\Policies\Microsoft\Edge"),
                       ("Brave", r"SOFTWARE\Policies\BraveSoftware\Brave"),
                       ("Chromium", r"SOFTWARE\Policies\Chromium"),
                       ("Vivaldi", r"SOFTWARE\Policies\Vivaldi"),
                       ("Yandex Browser", r"SOFTWARE\Policies\YandexBrowser")]
# Old roots Windows ships in its own store outside Microsoft's root program, for old signatures
WINDOWS_ROOTS = {"245C97DF7514E7CF2DF8BE72AE957B9E04741E85", "7F88CD7223F3C813818C994614A89C99FA3B5247",
                 "BE36A4562FB2EE05DBB3D32323ADF445084ED656", "A43489159A520F0D93D032CCAF37E7FE20A8B419"}
# Remote control programs: scammers who call "from support" ask to install one of these. Game streaming (Parsec,
# Sunshine, Steam Link) and Windows' own Quick Assist are not listed
REMOTE_TOOLS = [(re.compile(pattern, re.IGNORECASE), name) for pattern, name in (
    (r"^anydesk", "AnyDesk"), (r"^teamviewer", "TeamViewer"), (r"^rustdesk", "RustDesk"),
    (r"screenconnect|connectwise control", "ScreenConnect"), (r"^splashtop", "Splashtop"),
    (r"^logmein", "LogMeIn"), (r"^ultraviewer", "UltraViewer"), (r"^supremo", "Supremo"),
    (r"^aeroadmin", "AeroAdmin"), (r"^ammyy", "Ammyy Admin"), (r"netsupport", "NetSupport"),
    (r"^atera", "Atera"), (r"mesh ?agent", "MeshAgent"), (r"^tightvnc", "TightVNC"), (r"^ultravnc", "UltraVNC"),
    (r"^vnc server|realvnc server", "RealVNC Server"), (r"chrome remote desktop host", "Chrome Remote Desktop"),
    (r"^remote utilities.*host", "Remote Utilities"), (r"^radmin server", "Radmin Server"),
    (r"^dwagent|dwservice", "DWService"), (r"^zoho assist", "Zoho Assist"))]
TIME_DAYS = 14  # the clock: Windows synchronises it at least weekly


class Size(int):
    """Bytes: the window shows them as "640 MB" or "1.4 GB"."""


class Text(str):
    """The key of another "diag_lines" text, filled in with the same values: "kind_retry" -> "repeated reads"."""


class Finding:
    """The result of one check. line is the key of the one-line summary in the "diag_lines" texts, params fill
    it in; items are extra lines (key, params) shown in the details; actions are keys of ACTIONS."""

    def __init__(self, check, severity, line, params=None, items=(), actions=()):
        self.check = check
        self.group = GROUP_OF[check]
        self.severity = severity
        self.line = line
        self.params = params or {}
        self.items = list(items)
        self.actions = list(actions)

    def __repr__(self):
        return f"Finding({self.check!r}, {self.severity!r}, {self.line!r}, {self.params!r})"


def action_target(action):
    """(kind, target, arguments) of an action, with the folders of this PC filled in."""
    kind, target, args = ACTIONS[action]
    fill = {"%TEMP%": temp_dir(), "%HOSTS%": hosts_path()}
    return kind, fill.get(target, target), fill.get(args, args)


def unknown(check, line="unknown_read"):
    return Finding(check, "unknown", line)


# --- Facts ---

def _read(path, name):
    """A registry value, or None if it is missing or cannot be read."""
    try:
        found = engine.read_value(path, name)
    except OSError:
        return None
    return found[0] if found else None


def _subkeys(hive, path):
    try:
        with winreg.OpenKey(hive, path, 0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as key:
            return [winreg.EnumKey(key, i) for i in range(winreg.QueryInfoKey(key)[0])]
    except OSError:
        return []


def _values(hive, path):
    try:
        with winreg.OpenKey(hive, path, 0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as key:
            return [winreg.EnumValue(key, i)[:2] for i in range(winreg.QueryInfoKey(key)[1])]
    except OSError:
        return []


def memory():
    status = sysinfo.memory_status()
    if status is None:
        return None
    return {"total": status.ullTotalPhys, "avail": status.ullAvailPhys, "load": status.dwMemoryLoad,
            "commit_total": status.ullTotalPageFile, "commit_avail": status.ullAvailPageFile}


MEMORY_MANAGEMENT = r"HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Memory Management"


def pagefile():
    """The page files Windows is set to create, [] when the page file is off, and the ones it did create."""
    files = _read(MEMORY_MANAGEMENT, "PagingFiles")
    if files is None:
        return None
    existing = _read(MEMORY_MANAGEMENT, "ExistingPageFiles")

    def lines(value):
        return [line for line in (value if isinstance(value, list) else [value or ""]) if line.strip()]

    return {"files": lines(files), "existing": lines(existing) if existing is not None else None}


def page_file_entry(line):
    """("C:", initial MB, maximum MB) of a PagingFiles line; 0 0 is a size Windows manages, "?:" any drive."""
    parts = line.split()
    drive = parts[0][:2].upper() if parts else "?:"
    sizes = [int(p) for p in parts[1:3] if p.isdigit()]
    return drive, sizes[0] if sizes else 0, sizes[1] if len(sizes) > 1 else 0


class _PerformanceInfo(ctypes.Structure):
    _fields_ = [("cb", wintypes.DWORD)] + [(name, ctypes.c_size_t) for name in (
        "CommitTotal", "CommitLimit", "CommitPeak", "PhysicalTotal", "PhysicalAvailable", "SystemCache", "KernelTotal",
        "KernelPaged", "KernelNonpaged", "PageSize")] + [(name, wintypes.DWORD) for name in (
            "HandleCount", "ProcessCount", "ThreadCount")]


def kernel_pool():
    """Memory Windows' own drivers hold that can never move to the page file (the non-paged pool), in bytes."""
    info = _PerformanceInfo()
    info.cb = ctypes.sizeof(info)
    if not ctypes.windll.psapi.GetPerformanceInfo(ctypes.byref(info), info.cb):
        return None
    return {"nonpaged": info.KernelNonpaged * info.PageSize, "paged": info.KernelPaged * info.PageSize}


def process_title(name):
    pseudo = {"system": "System", "registry": "Registry", "memory compression": "Memory Compression",
              "secure system": "Secure System"}
    return pseudo.get(name, name + ".exe")


def programs_by_memory(api):
    """[(program, bytes)] of every running program, heaviest first. SimpleTool itself is left out."""
    totals, own = {}, os.getpid()
    for pid, name in api.processes():
        if pid in (0, own):
            continue
        totals[name] = totals.get(name, 0) + (api.working_set(pid) or 0)
    return sorted(((process_title(n), b) for n, b in totals.items()), key=lambda item: item[1], reverse=True)


def _filetime(ft):
    return ft.dwHighDateTime << 32 | ft.dwLowDateTime


def _system_times():
    idle, kernel, user = wintypes.FILETIME(), wintypes.FILETIME(), wintypes.FILETIME()
    if not ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user)):
        return None
    return _filetime(idle), _filetime(kernel) + _filetime(user)  # kernel time includes the idle time


class _ProcessorTimes(ctypes.Structure):  # SYSTEM_PROCESSOR_PERFORMANCE_INFORMATION, in 100 ns
    _fields_ = [("idle", ctypes.c_longlong), ("kernel", ctypes.c_longlong), ("user", ctypes.c_longlong),
                ("dpc", ctypes.c_longlong), ("interrupt", ctypes.c_longlong), ("count", wintypes.ULONG)]


def processor_times():
    """[(time, time spent in hardware interrupts and deferred procedure calls)] of each logical processor of this
    processor group since Windows started. Kernel time includes idle time and the interrupt time."""
    found = (_ProcessorTimes * 256)()
    size = wintypes.ULONG()
    if ctypes.windll.ntdll.NtQuerySystemInformation(8, found, ctypes.sizeof(found), ctypes.byref(size)) != 0:
        return None
    return [(t.kernel + t.user, t.dpc + t.interrupt) for t in found[:size.value // ctypes.sizeof(_ProcessorTimes)]]


def interrupt_share(before, after=None):
    """The highest share (%) of one logical processor's time taken by interrupts: since Windows started, or between
    two readings of processor_times()."""
    if not before:
        return None
    pairs = zip(before, after) if after else (((0, 0), t) for t in before)
    shares = [100.0 * (b[1] - a[1]) / (b[0] - a[0]) for a, b in pairs if b[0] > a[0]]
    return round(max(shares), 1) if shares else None


def cpu(api, seconds=CPU_SAMPLE):
    """Processor load over a short interval and the programs that used it: {"load": %, "top": [(name, %)]}, and the
    highest share of a logical processor that interrupts take, since Windows started and over the interval.
    SimpleTool itself is left out of the programs."""
    start = _system_times()
    times = processor_times()
    processes = [(pid, name) for pid, name in api.processes() if pid not in (0, os.getpid())]
    before = {pid: api.cpu_time(pid) for pid, _ in processes}
    time.sleep(seconds)
    end = _system_times()
    times_after = processor_times()
    if not start or not end or end[1] <= start[1]:
        return None
    total = end[1] - start[1]
    load = 100.0 * (1 - (end[0] - start[0]) / total)
    used = {}
    for pid, name in processes:
        after = api.cpu_time(pid)
        if after is not None and before.get(pid) is not None and after >= before[pid]:
            used[name] = used.get(name, 0) + after - before[pid]
    top = sorted(((process_title(n), 100.0 * t / total) for n, t in used.items()), key=lambda item: -item[1])
    return {"load": max(0.0, min(100.0, load)), "top": [item for item in top if item[1] >= 1][:5],
            "interrupts": interrupt_share(times_after or times),
            "interrupts_now": interrupt_share(times, times_after) if times and times_after else None}


CPU_KEY = r"HKLM\HARDWARE\DESCRIPTION\System\CentralProcessor\0"


def processor():
    """The processor's name, its model number and the microcode revision Windows loaded."""
    identifier = _read(CPU_KEY, "Identifier") or ""
    model = re.search(r"Model (\d+)", identifier)
    revision = _read(CPU_KEY, "Update Revision")
    if isinstance(revision, bytes) and len(revision) in (4, 8):
        # Eight bytes keep the revision in the upper half
        revision = int.from_bytes(revision[4:8] if len(revision) == 8 else revision, "little")
    else:
        revision = None
    name = " ".join((_read(CPU_KEY, "ProcessorNameString") or "").split())
    return {"name": name, "model": int(model.group(1)) if model else None, "microcode": revision}


class _Guid(ctypes.Structure):
    _fields_ = [("data", ctypes.c_ubyte * 16)]


def _guid(text):
    guid = _Guid()
    guid.data[:] = uuid.UUID(text).bytes_le
    return guid


class _PowerStatus(ctypes.Structure):
    _fields_ = [("ACLineStatus", ctypes.c_ubyte), ("BatteryFlag", ctypes.c_ubyte),
                ("BatteryLifePercent", ctypes.c_ubyte), ("SystemStatusFlag", ctypes.c_ubyte),
                ("BatteryLifeTime", wintypes.DWORD), ("BatteryFullLifeTime", wintypes.DWORD)]


def power():
    """The power plan, the Windows 11 power mode, the processor limits while plugged in, the power source and
    battery saver."""
    powrprof = ctypes.WinDLL("powrprof")
    pointer = ctypes.POINTER(_Guid)()
    if powrprof.PowerGetActiveScheme(None, ctypes.byref(pointer)):
        return None
    limits = dict.fromkeys(PROCESSOR_SETTINGS)
    try:
        scheme = str(uuid.UUID(bytes_le=bytes(pointer.contents.data)))
        size = wintypes.DWORD(0)
        powrprof.PowerReadFriendlyName(None, pointer, None, None, None, ctypes.byref(size))
        buffer = ctypes.create_string_buffer(size.value + 2)
        name = None
        if not powrprof.PowerReadFriendlyName(None, pointer, None, None, buffer, ctypes.byref(size)):
            name = ctypes.wstring_at(buffer) or None
        subgroup = _guid(PROCESSOR_SUBGROUP)
        for key, setting in PROCESSOR_SETTINGS.items():
            value = wintypes.DWORD()
            # A setting the plan does not have (hidden, or not for this processor) gives an error and stays None
            if not powrprof.PowerReadACValueIndex(None, pointer, ctypes.byref(subgroup), ctypes.byref(_guid(setting)),
                                                  ctypes.byref(value)):
                limits[key] = value.value
    finally:
        ctypes.windll.kernel32.LocalFree(pointer)
    overlay = None
    try:
        guid = _Guid()
        if not powrprof.PowerGetEffectiveOverlayScheme(ctypes.byref(guid)):
            overlay = str(uuid.UUID(bytes_le=bytes(guid.data)))
    except AttributeError:  # Windows 10 before 1709
        pass
    status = _PowerStatus()
    plugged, battery, saver = None, False, False
    if ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(status)):
        plugged = {0: False, 1: True}.get(status.ACLineStatus)
        battery = status.BatteryFlag not in (128, 255)  # 128: no battery, 255: unknown
        saver = status.SystemStatusFlag == 1
    return dict(limits, scheme=scheme, name=name, overlay=overlay, plugged=plugged, battery=battery, saver=saver)


class _DevMode(ctypes.Structure):
    _fields_ = [("dmDeviceName", ctypes.c_wchar * 32), ("dmSpecVersion", wintypes.WORD),
                ("dmDriverVersion", wintypes.WORD), ("dmSize", wintypes.WORD), ("dmDriverExtra", wintypes.WORD),
                ("dmFields", wintypes.DWORD), ("dmPositionX", ctypes.c_long), ("dmPositionY", ctypes.c_long),
                ("dmDisplayOrientation", wintypes.DWORD), ("dmDisplayFixedOutput", wintypes.DWORD),
                ("dmColor", ctypes.c_short), ("dmDuplex", ctypes.c_short), ("dmYResolution", ctypes.c_short),
                ("dmTTOption", ctypes.c_short), ("dmCollate", ctypes.c_short), ("dmFormName", ctypes.c_wchar * 32),
                ("dmLogPixels", wintypes.WORD), ("dmBitsPerPel", wintypes.DWORD), ("dmPelsWidth", wintypes.DWORD),
                ("dmPelsHeight", wintypes.DWORD), ("dmDisplayFlags", wintypes.DWORD),
                ("dmDisplayFrequency", wintypes.DWORD), ("dmICMMethod", wintypes.DWORD),
                ("dmICMIntent", wintypes.DWORD), ("dmMediaType", wintypes.DWORD), ("dmDitherType", wintypes.DWORD),
                ("dmReserved1", wintypes.DWORD), ("dmReserved2", wintypes.DWORD),
                ("dmPanningWidth", wintypes.DWORD), ("dmPanningHeight", wintypes.DWORD)]


class _DisplayDevice(ctypes.Structure):
    _fields_ = [("cb", wintypes.DWORD), ("DeviceName", ctypes.c_wchar * 32), ("DeviceString", ctypes.c_wchar * 128),
                ("StateFlags", wintypes.DWORD), ("DeviceID", ctypes.c_wchar * 128),
                ("DeviceKey", ctypes.c_wchar * 128)]


def displays():
    """Every display on the desktop: its resolution, refresh rate and the highest rate it offers at that
    resolution."""
    user32 = ctypes.windll.user32
    found, index = [], 0
    while True:
        device = _DisplayDevice()
        device.cb = ctypes.sizeof(device)
        if not user32.EnumDisplayDevicesW(None, index, ctypes.byref(device), 0):
            break
        index += 1
        if not device.StateFlags & 0x1:  # DISPLAY_DEVICE_ATTACHED_TO_DESKTOP
            continue
        current = _DevMode()
        current.dmSize = ctypes.sizeof(current)
        if not user32.EnumDisplaySettingsW(device.DeviceName, -1, ctypes.byref(current)):  # ENUM_CURRENT_SETTINGS
            continue
        best, mode_index = 0, 0
        while mode_index < 5000:
            mode = _DevMode()
            mode.dmSize = ctypes.sizeof(mode)
            if not user32.EnumDisplaySettingsW(device.DeviceName, mode_index, ctypes.byref(mode)):
                break
            mode_index += 1
            interlaced = mode.dmDisplayFlags & 0x2  # DM_INTERLACED: half the lines per refresh
            if (mode.dmPelsWidth, mode.dmPelsHeight) == (current.dmPelsWidth, current.dmPelsHeight) and not interlaced:
                best = max(best, mode.dmDisplayFrequency)
        found.append({"number": len(found) + 1, "width": current.dmPelsWidth, "height": current.dmPelsHeight,
                      "hz": current.dmDisplayFrequency, "max_hz": best, "adapter": device.DeviceString,
                      "vendor": pci_vendor(device.DeviceID),
                      "primary": bool(device.StateFlags & 0x4)})  # DISPLAY_DEVICE_PRIMARY_DEVICE
    return found


def video_memory():
    """{adapter name: bytes of its own memory} as the drivers report it. The processor's graphics report none, or
    the share of the RAM set aside for them."""
    found = {}
    for number in range(16):  # the class key itself has a protected subkey, so the adapters are opened by number
        path = rf"HKLM\{sysinfo.DISPLAY_CLASS}\{number:04d}"
        name = _read(path, "DriverDesc")
        if not name:
            continue
        size = _read(path, "HardwareInformation.qwMemorySize")
        if size is None:
            size = _read(path, "HardwareInformation.MemorySize")
        if isinstance(size, bytes):
            size = int.from_bytes(size[:8], "little")
        if isinstance(size, int) and size > 0:
            found[name] = size
    return found


class _DevPropKey(ctypes.Structure):
    _fields_ = [("fmtid", ctypes.c_ubyte * 16), ("pid", wintypes.ULONG)]


PCI_LINK = "3ab22e31-8264-4b4e-9af5-a8d2d8e33e62"  # DEVPKEY_PciDevice_*: 10 current, 12 maximum link width


def pcie_width(instance):
    """(current, maximum) PCI Express lanes of a device by its instance ID, or None."""
    cfgmgr = ctypes.WinDLL("cfgmgr32")
    cfgmgr.CM_Locate_DevNodeW.argtypes = [ctypes.POINTER(wintypes.DWORD), wintypes.LPCWSTR, wintypes.ULONG]
    cfgmgr.CM_Get_DevNode_PropertyW.argtypes = [wintypes.DWORD, ctypes.POINTER(_DevPropKey),
                                                ctypes.POINTER(wintypes.ULONG), ctypes.c_void_p,
                                                ctypes.POINTER(wintypes.ULONG), wintypes.ULONG]
    node = wintypes.DWORD()
    if cfgmgr.CM_Locate_DevNodeW(ctypes.byref(node), instance, 0):
        return None
    widths = []
    for pid in (10, 12):
        key = _DevPropKey()
        key.fmtid[:] = uuid.UUID(PCI_LINK).bytes_le
        key.pid = pid
        kind, value, size = wintypes.ULONG(), wintypes.ULONG(), wintypes.ULONG(4)
        if cfgmgr.CM_Get_DevNode_PropertyW(node.value, ctypes.byref(key), ctypes.byref(kind), ctypes.byref(value),
                                           ctypes.byref(size), 0):
            return None
        widths.append(value.value)
    return tuple(widths) if all(widths) else None


def gpu_preferences():
    """Programs set to the power-saving graphics in Settings → Display → Graphics."""
    values = _values(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\DirectX\UserGpuPreferences")
    return [name for name, data in values if isinstance(data, str) and "GpuPreference=1;" in data.replace(" ", "")]


RUN_KEYS = [(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", "Run"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run", "Run"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Run", "Run32")]
APPROVED = r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved"
APP_TASKS = r"Software\Classes\Local Settings\Software\Microsoft\Windows\CurrentVersion\AppModel\SystemAppData"
APP_PACKAGES = r"Software\Classes\Local Settings\Software\Microsoft\Windows\CurrentVersion\AppModel\Repository\Packages"


def _approved(hive, kind):
    """Startup entries turned off in Task Manager or Settings: StartupApproved data starting with an odd byte."""
    return {name.lower() for name, data in _values(hive, rf"{APPROVED}\{kind}")
            if isinstance(data, bytes) and data and data[0] & 1}


def startup_programs():
    """Names of the programs that start with Windows: Run keys, Startup folders and Store apps."""
    names = []
    for hive, path, kind in RUN_KEYS:
        off = _approved(hive, kind)
        names += [name for name, data in _values(hive, path) if name and data and name.lower() not in off]
    folders = [(winreg.HKEY_CURRENT_USER, os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup")),
               (winreg.HKEY_LOCAL_MACHINE,
                os.path.expandvars(r"%ProgramData%\Microsoft\Windows\Start Menu\Programs\StartUp"))]
    for hive, folder in folders:
        off = _approved(hive, "StartupFolder")
        try:
            files = os.listdir(folder)
        except OSError:
            continue
        names += [os.path.splitext(f)[0] for f in files if f.lower() != "desktop.ini" and f.lower() not in off]
    # Store apps that start with Windows: State 2 is on, 4 is on by a policy
    for package in _subkeys(winreg.HKEY_CURRENT_USER, APP_TASKS):
        for task in _subkeys(winreg.HKEY_CURRENT_USER, rf"{APP_TASKS}\{package}"):
            state = dict(_values(winreg.HKEY_CURRENT_USER, rf"{APP_TASKS}\{package}\{task}")).get("State")
            if state in (2, 4):
                names.append(package.split("_")[0].rpartition(".")[2] or package)
    unique = []
    for name in names:
        if name.lower() not in {n.lower() for n in unique}:
            unique.append(name)
    return unique


def game_dvr():
    """Whether Xbox Game Bar records the last minutes of games all the time."""
    if _read(r"HKLM\SOFTWARE\Policies\Microsoft\Windows\GameDVR", "AllowGameDVR") == 0:
        return {"background": False}
    capture = _read(r"HKCU\Software\Microsoft\Windows\CurrentVersion\GameDVR", "AppCaptureEnabled")
    history = _read(r"HKCU\Software\Microsoft\Windows\CurrentVersion\GameDVR", "HistoricalCaptureEnabled")
    enabled = _read(r"HKCU\System\GameConfigStore", "GameDVR_Enabled")
    return {"background": history == 1 and capture != 0 and enabled != 0}


def game_bar():
    """Whether the Xbox Game Bar is installed and Game Mode is on: AMD's X3D driver relies on both."""
    installed = any(p.lower().startswith("microsoft.xboxgamingoverlay_")
                    for p in _subkeys(winreg.HKEY_CURRENT_USER, APP_PACKAGES))
    return {"installed": installed,
            "game_mode": _read(r"HKCU\Software\Microsoft\GameBar", "AutoGameModeEnabled") != 0}


SERVICES_KEY = r"SYSTEM\CurrentControlSet\Services"


def services_named(fragment):
    """Service and driver key names whose display name contains fragment (case aside)."""
    found = []
    for name in _subkeys(winreg.HKEY_LOCAL_MACHINE, SERVICES_KEY):
        display = _read(rf"HKLM\{SERVICES_KEY}\{name}", "DisplayName")
        if isinstance(display, str) and fragment.lower() in display.lower():
            found.append(name)
    return found


def service_running(name):
    scm = services._advapi.OpenSCManagerW(None, None, services.SC_MANAGER_CONNECT)
    try:
        return services.scan_service(scm, name).running == 4  # SERVICE_RUNNING
    finally:
        if scm:
            services._advapi.CloseServiceHandle(scm)


def x3d_support():
    """For a Ryzen 9 X3D: whether AMD's 3D V-Cache driver runs. Nothing for other processors."""
    return {"driver": any(service_running(name) for name in services_named("3D V-Cache"))}


class _CodeIntegrity(ctypes.Structure):
    _fields_ = [("Length", wintypes.ULONG), ("CodeIntegrityOptions", wintypes.ULONG)]


def code_integrity():
    """Windows' code integrity flags (CI_*), or None if they cannot be read. Needs no rights."""
    info = _CodeIntegrity()
    info.Length = ctypes.sizeof(info)
    status = ctypes.windll.ntdll.NtQuerySystemInformation(103, ctypes.byref(info), ctypes.sizeof(info), None)
    return info.CodeIntegrityOptions if status == 0 else None


def boot_options():
    """Boot options and debugging settings that slow Windows down or make it unstable."""
    options = (_read(r"HKLM\SYSTEM\CurrentControlSet\Control", "SystemStartOptions") or "").upper().split()
    frequency = ctypes.c_longlong()
    ctypes.windll.kernel32.QueryPerformanceFrequency(ctypes.byref(frequency))
    return {"options": options,
            "verifier": bool(_read(MEMORY_MANAGEMENT, "VerifyDrivers")),
            "tdr_off": _read(r"HKLM\SYSTEM\CurrentControlSet\Control\GraphicsDrivers", "TdrLevel") == 0,
            "processors": os.cpu_count(),
            "integrity": code_integrity(),
            "timer": frequency.value}


def uptime():
    kernel32 = ctypes.windll.kernel32
    kernel32.GetTickCount64.restype = ctypes.c_ulonglong
    return kernel32.GetTickCount64() / 1000


def fast_startup():
    return (_read(r"HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Power", "HiberbootEnabled") == 1 and
            _read(r"HKLM\SYSTEM\CurrentControlSet\Control\Power", "HibernateEnabled") != 0)


def drives():
    """Fixed drives with a letter: their size and free space."""
    found = []
    system = os.environ.get("SystemDrive", "C:").upper()
    mask = ctypes.windll.kernel32.GetLogicalDrives()
    for i in range(26):
        if not mask >> i & 1:
            continue
        root = chr(65 + i) + ":\\"
        if ctypes.windll.kernel32.GetDriveTypeW(root) != 3:  # DRIVE_FIXED
            continue
        free, total = ctypes.c_ulonglong(), ctypes.c_ulonglong()
        if not ctypes.windll.kernel32.GetDiskFreeSpaceExW(root, None, ctypes.byref(total), ctypes.byref(free)):
            continue
        found.append({"drive": root[:2], "total": total.value, "free": free.value, "system": root[:2] == system})
    return found


def folder_size(path, budget=TEMP_BUDGET):
    """{"size": bytes, "files": count, "partial": whether the time ran out first}. Links are not followed."""
    size, files, stack, deadline = 0, 0, [path], time.monotonic() + budget
    while stack:
        if time.monotonic() > deadline:
            return {"size": size, "files": files, "partial": True}
        try:
            with os.scandir(stack.pop()) as entries:
                for entry in entries:
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            stack.append(entry.path)
                        elif entry.is_file(follow_symlinks=False):
                            size += entry.stat(follow_symlinks=False).st_size
                            files += 1
                    except OSError:
                        continue
        except OSError:
            continue
    return {"size": size, "files": files, "partial": False}


def temp_report(path, budget=TEMP_BUDGET):
    """The temporary folder: its size and file count, the entries that take most ("top") and the families of loose
    files with the same name pattern ("families"), so that the program that litters can be named."""
    deadline = time.monotonic() + budget
    try:
        with os.scandir(path) as it:
            entries = list(it)
    except OSError:
        return None
    size = files = 0
    partial = False
    top, families = [], {}
    for entry in entries:
        if time.monotonic() > deadline:
            partial = True
            break
        try:
            if entry.is_dir(follow_symlinks=False):
                sub = folder_size(entry.path, max(0.05, deadline - time.monotonic()))
                partial = partial or sub["partial"]
                size, files = size + sub["size"], files + sub["files"]
                top.append({"name": entry.name + "\\", "size": sub["size"], "files": sub["files"]})
            elif entry.is_file(follow_symlinks=False):
                length = entry.stat(follow_symlinks=False).st_size
                size, files = size + length, files + 1
                top.append({"name": entry.name, "size": length, "files": 1})
                stem, extension = os.path.splitext(entry.name)
                pattern = stem[:8].lower() + "*" + extension.lower()
                family = families.setdefault(pattern, {"pattern": pattern, "n": 0, "size": 0})
                family["n"], family["size"] = family["n"] + 1, family["size"] + length
        except OSError:
            continue
    top.sort(key=lambda t: t["size"], reverse=True)
    ranked = sorted(families.values(), key=lambda f: f["n"], reverse=True)
    return {"size": size, "files": files, "partial": partial, "top": top[:5], "families": ranked[:3]}


class _DeviceNumber(ctypes.Structure):
    _fields_ = [("DeviceType", wintypes.DWORD), ("DeviceNumber", wintypes.DWORD), ("PartitionNumber", wintypes.DWORD)]


def system_disk():
    """The number of the physical disk Windows is on, as Get-PhysicalDisk numbers them. Asking a volume for its
    disk number needs no rights to read it, so this works without administrator rights too."""
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateFileW.restype = wintypes.HANDLE
    kernel32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
                                     wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    kernel32.DeviceIoControl.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD,
                                         ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD),
                                         ctypes.c_void_p]
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    drive = os.environ.get("SystemDrive", "C:")[:2]
    # No access asked: only the device's own information can be read. FILE_SHARE_READ | FILE_SHARE_WRITE, OPEN_EXISTING
    handle = kernel32.CreateFileW(rf"\\.\{drive}", 0, 3, None, 3, 0, None)
    if not handle or handle == wintypes.HANDLE(-1).value:
        return None
    try:
        number, returned = _DeviceNumber(), wintypes.DWORD()
        if not kernel32.DeviceIoControl(handle, 0x2D1080, None, 0, ctypes.byref(number), ctypes.sizeof(number),
                                        ctypes.byref(returned), None):  # IOCTL_STORAGE_GET_DEVICE_NUMBER
            return None
        return number.DeviceNumber
    finally:
        kernel32.CloseHandle(handle)


IOCTL_STORAGE_QUERY_PROPERTY, SMART_RCV_DRIVE_DATA = 0x2D1400, 0x7C088
GENERIC_READ, GENERIC_WRITE, FILE_FLAG_NO_BUFFERING = 0x80000000, 0x40000000, 0x20000000


def _disk_api():
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateFileW.restype = wintypes.HANDLE
    kernel32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
                                     wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    kernel32.DeviceIoControl.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD,
                                         ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD),
                                         ctypes.c_void_p]
    kernel32.GetDevicePowerState.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.BOOL)]
    kernel32.ReadFile.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD),
                                  ctypes.c_void_p]
    kernel32.VirtualAlloc.restype = ctypes.c_void_p
    kernel32.VirtualAlloc.argtypes = [ctypes.c_void_p, ctypes.c_size_t, wintypes.DWORD, wintypes.DWORD]
    kernel32.VirtualFree.argtypes = [ctypes.c_void_p, ctypes.c_size_t, wintypes.DWORD]
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    return kernel32


def _open_disk(kernel32, number, access=0, flags=0):
    # FILE_SHARE_READ | FILE_SHARE_WRITE, OPEN_EXISTING
    handle = kernel32.CreateFileW(rf"\\.\PhysicalDrive{number}", access, 3, None, 3, flags, None)
    return None if not handle or handle == wintypes.HANDLE(-1).value else handle


def parse_nvme_health(log):
    """The NVMe "SMART / Health Information" log page (02h): what the drive itself says about its health."""
    if len(log) < 200 or not any(log[:6]) and not any(log[128:144]):
        return None  # an empty page: the driver did not fill it in

    def counter(offset):  # 128-bit counters
        return int.from_bytes(log[offset:offset + 16], "little")

    kelvin = struct.unpack_from("<H", log, 1)[0]
    return {"kind": "nvme", "critical": log[0], "temperature": kelvin - 273 if kelvin else None,
            "spare": log[3], "spare_threshold": log[4], "used": log[5],
            "written": counter(48) * 512_000,  # thousands of 512-byte units
            "hours": counter(128), "unsafe": counter(144), "media_errors": counter(160),
            "hot_minutes": struct.unpack_from("<I", log, 196)[0]}  # above the critical temperature


def nvme_health(kernel32, handle):
    # STORAGE_PROPERTY_QUERY for StorageDeviceProtocolSpecificProperty (50), followed by
    # STORAGE_PROTOCOL_SPECIFIC_DATA: NVMe (3), a log page (2), page 02h, its 512 bytes right after these 40
    query = struct.pack("<II", 50, 0) + struct.pack("<10I", 3, 2, 2, 0, 40, 512, 0, 0, 0, 0) + bytes(512)
    buffer = ctypes.create_string_buffer(query, len(query))
    returned = wintypes.DWORD()
    if not kernel32.DeviceIoControl(handle, IOCTL_STORAGE_QUERY_PROPERTY, buffer, len(query), buffer, len(query),
                                    ctypes.byref(returned), None):
        return None
    # STORAGE_PROTOCOL_DATA_DESCRIPTOR: Version, Size, then the structure again; its data offset counts from itself
    raw = buffer.raw
    offset, length = struct.unpack_from("<II", raw, 8 + 16)
    if length < 512 or 8 + offset + 512 > len(raw):
        return None
    return parse_nvme_health(raw[8 + offset:8 + offset + 512])


ATA_REALLOCATED, ATA_PENDING, ATA_UNCORRECTABLE, ATA_HOURS = 0x05, 0xC5, 0xC6, 0x09


def parse_ata_smart(data):
    """{attribute: raw value} of SMART READ DATA: a 2-byte version, then 30 slots of 12 bytes (id, flags, value,
    worst, 6 bytes raw, reserved)."""
    found = {}
    for slot in range(30):
        entry = data[2 + slot * 12:14 + slot * 12]
        if len(entry) == 12 and entry[0]:
            found[entry[0]] = int.from_bytes(entry[5:11], "little")
    if not found:
        return None
    return {"kind": "ata", "reallocated": found.get(ATA_REALLOCATED), "pending": found.get(ATA_PENDING),
            "uncorrectable": found.get(ATA_UNCORRECTABLE),
            "hours": found[ATA_HOURS] & 0xFFFFFFFF if ATA_HOURS in found else None}


def ata_smart(kernel32, handle, number):
    # SENDCMDINPARAMS without its 1-byte buffer: buffer size, IDEREGS for SMART READ DATA (features D0, the SMART
    # signature 4F C2 in the cylinder registers, command B0), the drive number and reserved bytes
    registers = bytes([0xD0, 1, 1, 0x4F, 0xC2, 0xA0 | ((number & 1) << 4), 0xB0, 0])
    params = struct.pack("<I", 512) + registers + bytes([number & 0xFF]) + bytes(19)
    out = ctypes.create_string_buffer(16 + 512)  # SENDCMDOUTPARAMS: size, DRIVERSTATUS, then the data
    returned = wintypes.DWORD()
    if not kernel32.DeviceIoControl(handle, SMART_RCV_DRIVE_DATA, params, len(params), out, len(out),
                                    ctypes.byref(returned), None):
        return None
    return parse_ata_smart(out.raw[16:16 + 512])


def drive_health(disks):
    """{disk number: health} that NVMe drives and SATA hard disks report themselves, as CrystalDiskInfo reads it.
    Windows' own counters (MSFT_StorageReliabilityCounter) leave out most of it and can report no wear at all.
    USB drives are left alone (some bridges hang on these requests), and so are hard disks that are spun down:
    reading them would wake them up."""
    kernel32 = _disk_api()
    found = {}
    for disk in disks:
        number, bus, media = disk.get("id"), (disk.get("bus") or "").upper(), (disk.get("media") or "").upper()
        if not str(number).isdigit():
            continue
        if bus in ("NVME", "RAID"):
            handle = _open_disk(kernel32, number)
            if handle:
                try:
                    health = nvme_health(kernel32, handle)
                finally:
                    kernel32.CloseHandle(handle)
                if health:
                    found[str(number)] = health
        elif bus in ("SATA", "ATA") and media == "HDD":
            handle = _open_disk(kernel32, number, GENERIC_READ | GENERIC_WRITE)  # administrators only
            if not handle:
                continue
            try:
                awake = wintypes.BOOL(True)
                if kernel32.GetDevicePowerState(handle, ctypes.byref(awake)) and not awake.value:
                    continue
                health = ata_smart(kernel32, handle, int(number))
            finally:
                kernel32.CloseHandle(handle)
            if health:
                found[str(number)] = health
    return found


def disk_instance(path):
    """The device instance of a disk from its MSFT_Disk path:
    \\\\?\\scsi#disk&ven_nvme&prod_x#5&1&0&000000#{guid} -> SCSI\\DISK&VEN_NVME&PROD_X\\5&1&0&000000."""
    parts = (path or "").replace("\\\\?\\", "").split("#")
    return "\\".join(parts[:3]).upper() if len(parts) >= 4 else None


def _devnode(cfgmgr, instance):
    node = wintypes.DWORD()
    return node.value if not cfgmgr.CM_Locate_DevNodeW(ctypes.byref(node), instance, 0) else None


def _cfgmgr():
    cfgmgr = ctypes.WinDLL("cfgmgr32")
    cfgmgr.CM_Locate_DevNodeW.argtypes = [ctypes.POINTER(wintypes.DWORD), wintypes.LPCWSTR, wintypes.ULONG]
    cfgmgr.CM_Get_Parent.argtypes = [ctypes.POINTER(wintypes.DWORD), wintypes.DWORD, wintypes.ULONG]
    cfgmgr.CM_Get_DevNode_PropertyW.argtypes = [wintypes.DWORD, ctypes.POINTER(_DevPropKey),
                                                ctypes.POINTER(wintypes.ULONG), ctypes.c_void_p,
                                                ctypes.POINTER(wintypes.ULONG), wintypes.ULONG]
    return cfgmgr


def _pci_properties(cfgmgr, node, pids):
    values = []
    for pid in pids:
        key = _DevPropKey()
        key.fmtid[:] = uuid.UUID(PCI_LINK).bytes_le
        key.pid = pid
        kind, value, size = wintypes.ULONG(), wintypes.ULONG(), wintypes.ULONG(4)
        if cfgmgr.CM_Get_DevNode_PropertyW(node, ctypes.byref(key), ctypes.byref(kind), ctypes.byref(value),
                                           ctypes.byref(size), 0):
            return None
        values.append(value.value)
    return values if all(values) else None


def _busy_reads(kernel32, number, seconds):
    """Reads the drive from its start for a moment, so a link that saves power at rest runs at full speed."""
    handle = _open_disk(kernel32, number, GENERIC_READ, FILE_FLAG_NO_BUFFERING)
    if not handle:
        return
    size = 4 * MB
    buffer = kernel32.VirtualAlloc(None, size, 0x3000, 0x04)  # MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE
    try:
        done, end = wintypes.DWORD(), time.monotonic() + seconds
        while buffer and time.monotonic() < end:
            if not kernel32.ReadFile(handle, buffer, size, ctypes.byref(done), None) or not done.value:
                break
    finally:
        if buffer:
            kernel32.VirtualFree(buffer, 0, 0x8000)  # MEM_RELEASE
        kernel32.CloseHandle(handle)


def drive_links(disks, paths):
    """{disk number: (generation, lanes, highest generation, most lanes)} of the PCI Express link of each NVMe
    drive (generation 3 is PCIe 3.0). A link below the drive's best is read again while the drive is busy, because
    some links slow down at rest to save power; that needs administrator rights."""
    cfgmgr, kernel32 = _cfgmgr(), _disk_api()
    nvme = {str(d.get("id")) for d in disks if (d.get("bus") or "").upper() == "NVME"}
    found = {}
    for entry in paths:
        number = str(entry.get("number"))
        instance = disk_instance(entry.get("path"))
        disk_node = _devnode(cfgmgr, instance) if number in nvme and instance else None
        parent = wintypes.DWORD()
        if disk_node is None or cfgmgr.CM_Get_Parent(ctypes.byref(parent), disk_node, 0):
            continue
        link = _pci_properties(cfgmgr, parent.value, (9, 10, 11, 12))  # current speed, width; maximum speed, width
        if not link:
            continue
        if link[0] < link[2] or link[1] < link[3]:
            if not engine.is_admin():
                link[0] = link[2]  # the generation at rest says nothing without reading the drive: not judged
            else:
                reader = threading.Thread(target=_busy_reads, args=(kernel32, number, 0.3), daemon=True)
                reader.start()
                while reader.is_alive():
                    again = _pci_properties(cfgmgr, parent.value, (9, 10)) or link[:2]
                    link[0], link[1] = max(link[0], again[0]), max(link[1], again[1])
                    time.sleep(0.02)
        found[number] = tuple(link)
    return found


STARTUP_INFO = r"%SystemRoot%\System32\wdi\LogFiles\StartupInfo"


def startup_trees(data):
    """[(program, processor µs, bytes read)] of one StartupInfo file: each program that started with Windows,
    with what the programs it started used."""
    processes = {}
    for process in ElementTree.fromstring(data).iter("Process"):
        try:
            processes[process.get("PID")] = {"name": process.get("Name") or "",
                                             "parent": (process.findtext("ParentPID") or "").strip(),
                                             "cpu": int(process.findtext("CpuUsage") or 0),
                                             "disk": int(process.findtext("DiskUsage") or 0)}
        except ValueError:
            continue
    sums = {}
    for pid, process in processes.items():
        top, seen = pid, {pid}
        while processes[top]["parent"] in processes and processes[top]["parent"] not in seen:
            top = processes[top]["parent"]
            seen.add(top)
        cpu_time, disk = sums.get(processes[top]["name"], (0, 0))
        sums[processes[top]["name"]] = (cpu_time + process["cpu"], disk + process["disk"])
    return [(name, cpu_time, disk) for name, (cpu_time, disk) in sums.items() if name]


def startup_impact():
    """[{"name", "cpu" (ms), "disk" (bytes), "starts"}] of the programs that start with Windows, on average over the
    last starts Windows measured (up to five), as Task Manager's "Startup impact" counts them: the processor time
    and the data read from the drive, the programs they started included. Windows' own programs are left out. The
    files are per account; the newest are the account at the PC. Needs administrator rights."""
    folder = os.path.expandvars(STARTUP_INFO)
    try:
        files = [os.path.join(folder, name) for name in os.listdir(folder) if name.lower().endswith(".xml")]
    except OSError:
        return None
    accounts = {}
    for path in files:
        accounts.setdefault(os.path.basename(path).split("_")[0], []).append(path)
    if not accounts:
        return []
    newest = max(accounts.values(), key=lambda group: max(os.path.getmtime(p) for p in group))
    totals = {}
    for path in newest:
        try:
            with open(path, "rb") as f:
                trees = startup_trees(f.read())
        except (OSError, SyntaxError):  # ElementTree.ParseError is a SyntaxError
            continue
        for name, cpu_time, disk in trees:
            totals.setdefault(name, []).append((cpu_time, disk))
    windows_folder = os.path.normcase(os.environ.get("SystemRoot", r"C:\Windows")) + os.sep
    found = []
    for path, runs in totals.items():
        if os.path.normcase(path).startswith(windows_folder):
            continue
        found.append({"name": file_description(path) or os.path.splitext(os.path.basename(path))[0],
                      "cpu": sum(r[0] for r in runs) // len(runs) // 1000, "disk": sum(r[1] for r in runs) // len(runs),
                      "starts": len(runs)})
    return sorted(found, key=lambda item: (-item["cpu"], -item["disk"]))


def temp_dir():
    return os.environ.get("TEMP") or os.environ.get("TMP") or ""


def trim_off():
    """Whether Windows has stopped telling SSDs which blocks are free (TRIM) on NTFS drives."""
    return _read(r"HKLM\SYSTEM\CurrentControlSet\Control\FileSystem", "DisableDeleteNotification") == 1


def restart_pending():
    return any(engine.key_exists(path) for path in (
        r"HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending",
        r"HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired"))


def update_settings():
    """Whether the Windows Update service is disabled, automatic updates are turned off by a policy, updates are
    taken from another server (WSUS) or blocked by policies, and until when they are paused."""
    server = _read(WU_POLICY, "WUServer") if _read(WU_POLICY + r"\AU", "UseWUServer") == 1 else None
    return {"disabled": _read(r"HKLM\SYSTEM\CurrentControlSet\Services\wuauserv", "Start") == 4,
            "policy_off": _read(WU_POLICY + r"\AU", "NoAutoUpdate") == 1,
            "server": server.strip() if isinstance(server, str) and server.strip() else None,
            "blocked": [name for name in ("DisableWindowsUpdateAccess", "DoNotConnectToWindowsUpdateInternetLocations",
                                          "SetDisableUXWUAccess") if _read(WU_POLICY, name) == 1],
            "paused_until": update_pause()}


def update_pause():
    """Until when quality updates are paused (local time), or None. Settings writes UTC times like
    "2026-11-20T09:00:00Z"."""
    latest = None
    for name in ("PauseUpdatesExpiryTime", "PauseQualityUpdatesEndTime"):
        value = _read(r"HKLM\SOFTWARE\Microsoft\WindowsUpdate\UX\Settings", name)
        if not isinstance(value, str) or not value.strip():
            continue
        try:
            moment = datetime.datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            continue
        if moment.tzinfo:
            moment = moment.astimezone().replace(tzinfo=None)
        latest = max(latest, moment) if latest else moment
    return latest


PACKAGES = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\Packages"


def last_windows_update():
    """When the newest monthly Windows update was installed (local time), from the servicing store. The Windows
    Update service's own "last installed" date also moves with Microsoft Store apps."""
    newest = None
    for name in _subkeys(winreg.HKEY_LOCAL_MACHINE, PACKAGES):
        if not name.startswith("Package_for_RollupFix"):
            continue
        path = rf"HKLM\{PACKAGES}\{name}"
        if _read(path, "CurrentState") != 112:  # installed; a replaced one is 80
            continue
        high, low = _read(path, "InstallTimeHigh"), _read(path, "InstallTimeLow")
        if not isinstance(high, int) or not isinstance(low, int):
            continue
        utc = datetime.datetime(1601, 1, 1) + datetime.timedelta(microseconds=(high << 32 | low) // 10)
        moment = utc.replace(tzinfo=datetime.timezone.utc).astimezone().replace(tzinfo=None)
        newest = max(newest, moment) if newest else moment
    return newest


def proxy():
    path = r"HKCU\Software\Microsoft\Windows\CurrentVersion\Internet Settings"
    return {"enabled": _read(path, "ProxyEnable") == 1, "server": _read(path, "ProxyServer") or "",
            "pac": _read(path, "AutoConfigURL") or ""}


def hosts_path():
    return os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "drivers", "etc", "hosts")


def hosts():
    """How many names the hosts file redirects (localhost aside), and the ones Windows needs among them."""
    try:
        with open(hosts_path(), encoding="utf-8", errors="replace") as f:
            lines = f.read(2 * 1024 * 1024).splitlines()
    except FileNotFoundError:
        return {"entries": 0, "blocked": []}
    entries, blocked = 0, []
    for line in lines:
        parts = line.split("#", 1)[0].split()
        if len(parts) < 2:
            continue
        for name in (n.lower() for n in parts[1:]):
            if name in ("localhost", "localhost.localdomain", "local", "broadcasthost"):
                continue
            entries += 1
            if any(name == d or name.endswith("." + d) for d in NEEDED_DOMAINS):
                blocked.append(name)
    return {"entries": entries, "blocked": blocked}


def windows():
    product, version, build, edition = sysinfo.release()
    key = rf"HKLM\{sysinfo.WINDOWS_KEY}"
    system32 = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32")
    return {"product": product, "version": version, "build": build, "edition": edition or "",
            "update": _read(key, "UBR") or 0,
            "server": (_read(key, "InstallationType") or "").lower() == "server",
            "media": os.path.exists(os.path.join(system32, "mfplat.dll"))}


def _service_start(name):
    return _read(rf"HKLM\{SERVICES_KEY}\{name}", "Start")


def display_name(name):
    """A service's name as Windows shows it: "@%SystemRoot%\\system32\\qmgr.dll,-1000" is looked up in the DLL."""
    display = _read(rf"HKLM\{SERVICES_KEY}\{name}", "DisplayName")
    if not isinstance(display, str) or not display:
        return name
    if display.startswith("@"):
        buffer = ctypes.create_unicode_buffer(512)
        if ctypes.windll.shlwapi.SHLoadIndirectString(display, buffer, len(buffer), None) != 0:
            return name
        display = buffer.value
    return display or name


def disabled_services():
    """[(service, display name, effect)] of the services in CORE_SERVICES and OPTIONAL_SERVICES that are disabled,
    and the clock when it is set never to synchronise."""
    found = [(name, display_name(name), effect) for name, effect in CORE_SERVICES + OPTIONAL_SERVICES
             if _service_start(name) == 4]
    if _service_start("W32Time") != 4 and \
            (_read(r"HKLM\SYSTEM\CurrentControlSet\Services\W32Time\Parameters", "Type") or "").lower() == "nosync":
        found.append(("W32Time", display_name("W32Time"), "clock"))
    if _service_start("SysMain") == 4:
        found.append(("SysMain", display_name("SysMain"), "compression"))
    return found


def wer_off():
    """Whether Windows Error Reporting is turned off: then hangs of the graphics card are not recorded."""
    return (_read(r"HKLM\SOFTWARE\Policies\Microsoft\Windows\Windows Error Reporting", "Disabled") == 1 or
            _read(r"HKLM\SOFTWARE\Microsoft\Windows\Windows Error Reporting", "Disabled") == 1 or
            _service_start("WerSvc") == 4)


def file_version(path):
    """(major, minor, build, revision) of a DLL or exe, or None if it is not there."""
    version = ctypes.windll.version
    size = version.GetFileVersionInfoSizeW(path, None)
    if not size:
        return None
    buffer = ctypes.create_string_buffer(size)
    if not version.GetFileVersionInfoW(path, 0, size, buffer):
        return None
    pointer, length = ctypes.c_void_p(), wintypes.UINT()
    if not version.VerQueryValueW(buffer, "\\", ctypes.byref(pointer), ctypes.byref(length)) or not pointer.value:
        return None
    fixed = (wintypes.DWORD * 4).from_address(pointer.value + 8)  # dwFileVersionMS and LS follow two DWORDs
    return fixed[0] >> 16, fixed[0] & 0xFFFF, fixed[1] >> 16, fixed[1] & 0xFFFF


def file_description(path):
    """A program's description from its version information ("Proton Mail Bridge"), or None."""
    version = ctypes.windll.version
    size = version.GetFileVersionInfoSizeW(path, None)
    if not size:
        return None
    buffer = ctypes.create_string_buffer(size)
    if not version.GetFileVersionInfoW(path, 0, size, buffer):
        return None
    pointer, length = ctypes.c_void_p(), wintypes.UINT()
    if not version.VerQueryValueW(buffer, "\\VarFileInfo\\Translation", ctypes.byref(pointer), ctypes.byref(length)) \
            or length.value < 4 or not pointer.value:
        return None
    language, codepage = struct.unpack("<HH", ctypes.string_at(pointer.value, 4))
    if not version.VerQueryValueW(buffer, f"\\StringFileInfo\\{language:04x}{codepage:04x}\\FileDescription",
                                  ctypes.byref(pointer), ctypes.byref(length)) or not length.value or not pointer.value:
        return None
    return ctypes.wstring_at(pointer.value, length.value).rstrip("\0").strip() or None


def vc_runtime():
    """The version of the Visual C++ runtime for 64-bit and 32-bit programs; None where it is not installed."""
    root = os.environ.get("SystemRoot", r"C:\Windows")
    return {"x64": file_version(os.path.join(root, "System32", "msvcp140.dll")),
            "x86": file_version(os.path.join(root, "SysWOW64", "msvcp140.dll"))
            if os.path.isdir(os.path.join(root, "SysWOW64")) else None}


class _TpmInfo(ctypes.Structure):
    _fields_ = [("structVersion", wintypes.UINT), ("tpmVersion", wintypes.UINT), ("tpmInterfaceType", wintypes.UINT),
                ("tpmImpRevision", wintypes.UINT)]


def firmware():
    """UEFI or legacy BIOS boot, Secure Boot and the TPM version (0 for none), all readable without rights."""
    kind = wintypes.DWORD()
    uefi = bool(ctypes.windll.kernel32.GetFirmwareType(ctypes.byref(kind))) and kind.value == 2
    secure = _read(r"HKLM\SYSTEM\CurrentControlSet\Control\SecureBoot\State", "UEFISecureBootEnabled")
    tpm = None
    try:
        info = _TpmInfo()
        info.structVersion = 1
        result = ctypes.WinDLL("tbs").Tbsi_GetDeviceInfo(ctypes.sizeof(info), ctypes.byref(info))
        tpm = info.tpmVersion if result == 0 else 0
    except OSError:
        pass
    anti_cheat = any(_service_start(name) is not None for name in ANTI_CHEAT_TPM)
    # The Secure Boot certificates of 2023 that replace those of 2011, which expired in 2026: Windows updates them
    # itself and keeps the state here (NotStarted, InProgress, Updated) with an error code when it failed
    servicing = r"HKLM\SYSTEM\CurrentControlSet\Control\SecureBoot\Servicing"
    status, error = _read(servicing, "UEFICA2023Status"), _read(servicing, "UEFICA2023Error")
    return {"uefi": uefi, "secure_boot": None if secure is None else secure == 1, "tpm": tpm,
            "anti_cheat": anti_cheat, "ca2023": status if isinstance(status, str) else None,
            "ca2023_error": error if isinstance(error, int) and error else None}


def security_settings():
    """Protections that "optimization" tools turn off: UAC, the Spectre and Meltdown mitigations, SmartScreen, the
    "downloaded from the internet" mark, Microsoft Defender through its policies, and Windows Security hidden."""
    explorer = _read(r"HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer", "SmartScreenEnabled")
    return {"uac_off": _read(r"HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System", "EnableLUA") == 0,
            "mitigations_off": _read(MEMORY_MANAGEMENT, "FeatureSettingsOverride") == 3 and
            _read(MEMORY_MANAGEMENT, "FeatureSettingsOverrideMask") == 3,
            "smartscreen_off": _read(r"HKLM\SOFTWARE\Policies\Microsoft\Windows\System", "EnableSmartScreen") == 0 or
            isinstance(explorer, str) and explorer.lower() == "off",
            "zone_off": any(_read(rf"{hive}\Software\Microsoft\Windows\CurrentVersion\Policies\Attachments",
                                  "SaveZoneInformation") == 1 for hive in ("HKCU", "HKLM")),
            "defender_policies": [name for path, name in DEFENDER_POLICIES if _read(path, name) == 1],
            "notifications_off": _read(r"HKLM\SOFTWARE\Policies\Microsoft\Windows Defender Security Center"
                                       r"\Notifications", "DisableNotifications") == 1,
            "hidden_pages": hidden_pages(),
            # Microsoft's list of vulnerable drivers Windows refuses to load (on by default since Windows 11 22H2)
            "blocklist_off": _read(r"HKLM\SYSTEM\CurrentControlSet\Control\CI\Config",
                                   "VulnerableDriverBlocklistEnable") == 0}


def hidden_pages():
    """The pages of HIDDEN_PAGES that a policy hides in Settings: "hide:windowsdefender;..." or "showonly:...". """
    hidden = []
    for hive in ("HKLM", "HKCU"):
        value = _read(rf"{hive}\Software\Microsoft\Windows\CurrentVersion\Policies\Explorer", "SettingsPageVisibility")
        if not isinstance(value, str):
            continue
        kind, _, pages = value.strip().lower().partition(":")
        listed = {page.strip() for page in pages.split(";") if page.strip()}
        if kind == "hide":
            hidden += [page for page in HIDDEN_PAGES if page in listed]
        elif kind == "showonly":
            hidden += [page for page in HIDDEN_PAGES if page not in listed]
    return list(dict.fromkeys(hidden))


# --- Traces of tweaking tools and malware: blocked programs, locked tools, removed parts of Windows ---

def managed():
    """Whether an organization manages this PC: joined to a domain or to Microsoft Entra ID, or enrolled in device
    management. A work or school account only added to Windows (the "workplace join") does not manage the PC."""
    netapi = ctypes.WinDLL("netapi32")
    domain = False
    name, status = ctypes.c_wchar_p(), ctypes.c_int()
    if netapi.NetGetJoinInformation(None, ctypes.byref(name), ctypes.byref(status)) == 0:
        domain = status.value == 3  # NetSetupDomainName
        netapi.NetApiBufferFree(name)
    entra = False
    try:
        info = ctypes.POINTER(ctypes.c_int)()  # DSREG_JOIN_INFO starts with joinType
        if netapi.NetGetAadJoinInformation(None, ctypes.byref(info)) == 0 and info:
            entra = info.contents.value == 1  # DSREG_DEVICE_JOIN; 2 is a work account added
            netapi.NetFreeAadJoinInformation(info)
    except AttributeError:  # before Windows 10 1607
        pass
    enrolled = False
    try:
        # A buffer for the account name it enrolled with: without one the call fails on an enrolled PC
        registered, account = wintypes.BOOL(), ctypes.create_unicode_buffer(256)
        if ctypes.WinDLL("mdmregistration").IsDeviceRegisteredWithManagement(ctypes.byref(registered), 256,
                                                                            account) == 0:
            enrolled = bool(registered.value)
    except (AttributeError, OSError):
        pass
    return {"domain": domain, "entra": entra, "mdm": enrolled}


def _is_managed(facts):
    return any((facts.get("managed") or {}).values())


def command_program(command):
    """The program a command line starts, with variables filled in: '"%windir%\\x.exe" /a' -> 'C:\\Windows\\x.exe'."""
    command = os.path.expandvars((command or "").strip())
    if command.startswith('"'):
        return command[1:].split('"', 1)[0]
    match = re.match(r"(.+?\.(?:exe|com|bat|cmd|scr))(?:\s|$)", command, re.IGNORECASE)
    if match:
        return match.group(1)
    return command.split()[0] if command.split() else ""


def _key_values(key, *names):
    found = []
    for name in names:
        try:
            found.append(winreg.QueryValueEx(key, name)[0])
        except OSError:
            found.append(None)
    return found


def ifeo_debuggers():
    """[(program, debugger)] of Image File Execution Options in the 64-bit and the 32-bit registry. A program can
    also have one filter per full path under its key (UseFilter), each with a debugger of its own."""
    found = []
    for view in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
        try:
            root = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, IFEO, 0, winreg.KEY_READ | view)
        except OSError:
            continue
        with root:
            for program in programs._subkeys(root):
                try:
                    with winreg.OpenKey(root, program) as key:
                        debugger, use_filter = _key_values(key, "Debugger", "UseFilter")
                        if isinstance(debugger, str) and debugger.strip():
                            found.append((program.lower(), debugger.strip()))
                        if use_filter == 1:
                            for sub in programs._subkeys(key):
                                with winreg.OpenKey(key, sub) as filtered:
                                    debugger = _key_values(filtered, "Debugger")[0]
                                    if isinstance(debugger, str) and debugger.strip():
                                        found.append((program.lower(), debugger.strip()))
                except OSError:
                    continue
    return list(dict.fromkeys(found))  # keys that are not redirected show up in both views


def _windows_program(name):
    root = os.environ.get("SystemRoot", r"C:\Windows")
    return any(os.path.isfile(os.path.join(root, *parts, name)) for parts in ((), ("System32",), ("SysWOW64",)))


def blocked_kind(program, debugger):
    """What a debugger set for a program means: "sign_in" (a program of the sign-in screen starts something else),
    "hijack" (a program from a user's folder starts instead), "protection" (protection or a tool to look for
    problems cannot start), "windows" (a Windows program is blocked), or None (a debugger or a replacement on
    purpose, or some other program)."""
    path = command_program(debugger)
    name = os.path.basename(path)
    replacement = DEBUGGER_REPLACEMENTS.get(program)
    if replacement and replacement.search(name) or DEVELOPER_DEBUGGERS.search(name):
        return None
    if program in SIGN_IN_PROGRAMS:
        return "sign_in"
    if USER_FOLDERS.search(path):
        return "hijack"
    if program in PROTECTION_PROGRAMS:
        return "protection"
    return "windows" if _windows_program(program) else None


def _services_of(names):
    """{program: [display names]} of the services that run one of these programs."""
    found = {}
    for service in _subkeys(winreg.HKEY_LOCAL_MACHINE, SERVICES_KEY):
        image = _read(rf"HKLM\{SERVICES_KEY}\{service}", "ImagePath")
        program = os.path.basename(command_program(image)).lower() if isinstance(image, str) else ""
        if program in names:
            found.setdefault(program, []).append(display_name(service))
    return found


def tool_locks():
    """[tool] that policies lock (TOOL_LOCKS), and the programs DisallowRun names."""
    locks, names = [], []
    for hive in ("HKCU", "HKLM"):
        for path, value, values, tool in TOOL_LOCKS:
            if _read(rf"{hive}\Software\{path}", value) in values and tool not in locks:
                locks.append(tool)
        listed = _values(winreg.HKEY_CURRENT_USER if hive == "HKCU" else winreg.HKEY_LOCAL_MACHINE,
                         r"Software\Microsoft\Windows\CurrentVersion\Policies\Explorer\DisallowRun")
        names += [data for _, data in listed if isinstance(data, str) and data.strip()]
    return locks, list(dict.fromkeys(names))


def firewall_blocks():
    """Programs of security software that an active rule of Windows Firewall blocks, by file name."""
    found = []
    for path in (FIREWALL_RULES, r"SOFTWARE\Policies\Microsoft\WindowsFirewall\FirewallRules"):
        for _, data in _values(winreg.HKEY_LOCAL_MACHINE, path):
            if not isinstance(data, str):
                continue
            fields = dict(part.split("=", 1) for part in data.split("|") if "=" in part)
            app = fields.get("App", "")
            if fields.get("Action") == "Block" and fields.get("Active", "").upper() == "TRUE" and \
                    SECURITY_VENDORS.search(app):
                found.append(os.path.basename(os.path.expandvars(app)))
    return sorted(set(found), key=str.lower)


def blocked_tools():
    """Programs blocked through Image File Execution Options (with the services that run them), locked tools and
    security software blocked in the firewall."""
    programs_found = []
    for program, debugger in ifeo_debuggers():
        kind = blocked_kind(program, debugger)
        if kind:
            programs_found.append({"program": program, "debugger": debugger, "kind": kind})
    services_by_program = _services_of({p["program"] for p in programs_found}) if programs_found else {}
    for found in programs_found:
        found["services"] = services_by_program.get(found["program"], [])
    locks, disallowed = tool_locks()
    return {"programs": programs_found, "locks": locks, "disallowed": disallowed, "firewall": firewall_blocks()}


def app_platform():
    """The Windows packages this account has, the ones removed for every new account, and the WebView2 runtime.
    None when SimpleTool runs as another account than the one signed in: then HKCU is that account's."""
    if engine.other_account():
        return None
    packages = [name.lower() for name in _subkeys(winreg.HKEY_CURRENT_USER, APP_PACKAGES)]
    if not packages:
        return None  # the list could not be read
    webview = None
    for path in WEBVIEW2_KEYS:
        version = _read(path, "pv")
        if isinstance(version, str) and version.strip() not in ("", "0.0.0.0"):
            webview = version.strip()
            break
    return {"packages": packages, "webview2": webview,
            "deprovisioned": [name.lower() for name in _subkeys(winreg.HKEY_LOCAL_MACHINE, DEPROVISIONED)],
            "gaming": any(p.startswith(GAMING_PACKAGES) for p in packages)}


def sleep_state():
    """Whether the PC has any way to sleep (S1-S3 or Modern Standby), and the settings known to take it away."""
    capabilities = ctypes.create_string_buffer(76)  # SYSTEM_POWER_CAPABILITIES
    if not ctypes.windll.powrprof.GetPwrCapabilities(capabilities):
        return None
    raw = capabilities.raw
    causes = []
    if _read(r"HKLM\SYSTEM\CurrentControlSet\Control\Power", "PlatformAoAcOverride") == 0:
        causes.append("aoac_override")  # Modern Standby turned off, on a PC that may have no S3 to fall back on
    if 0 in (_read(STANDBY_POLICY, "ACSettingIndex"), _read(STANDBY_POLICY, "DCSettingIndex")):
        causes.append("standby_policy")
    # SystemS1, SystemS2, SystemS3 at offsets 3-5, AoAc (Modern Standby) at 20
    return {"available": bool(raw[3] or raw[4] or raw[5] or raw[20]), "causes": causes}


def network_setup():
    """What networking in games relies on: IPv6 (DisabledComponents), Teredo set off by a policy, the IP Helper
    service, services merged into shared processes, and whether Xbox gaming is installed at all."""
    split = _read(r"HKLM\SYSTEM\CurrentControlSet\Control", SVCHOST_SPLIT)
    ipv6 = _read(r"HKLM\SYSTEM\CurrentControlSet\Services\Tcpip6\Parameters", "DisabledComponents")
    policy = _read(r"HKLM\SOFTWARE\Policies\Microsoft\Windows\TCPIP\v6Transition", "Teredo_State")
    packages = [name.lower() for name in _subkeys(winreg.HKEY_CURRENT_USER, APP_PACKAGES)]
    return {"ipv6": ipv6 if isinstance(ipv6, int) else 0, "split": split if isinstance(split, int) else None,
            "teredo_policy_off": isinstance(policy, str) and policy.lower() == "disabled",
            "ip_helper_off": _service_start("iphlpsvc") == 4,
            "gaming": _service_start("GamingServices") is not None or
            any(p.startswith(GAMING_PACKAGES) for p in packages)}


def wmi_repository():
    """The exit code of Windows' own check of the WMI repository (0: consistent). Needs administrator rights."""
    if not engine.is_admin():
        return None
    tool = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "wbem", "winmgmt.exe")
    try:
        done = subprocess.run([tool, "/verifyrepository"], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL, timeout=60, creationflags=engine.CREATE_NO_WINDOW,
                              env=engine.clean_env())
    except (OSError, subprocess.TimeoutExpired):
        return None
    return done.returncode & 0xFFFFFFFF


# --- Protection and recovery: Defender's exclusions, browser policies, trusted roots, accounts, exposure, WinRE ---

def recovery_environment():
    """Whether the Windows Recovery Environment is turned on, from the settings file reagentc keeps (its own output
    is in the language of Windows). None when the file cannot be read."""
    path = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "Recovery", "ReAgent.xml")
    try:
        with open(path, "rb") as f:
            state = ElementTree.fromstring(f.read()).find("InstallState")
    except (OSError, SyntaxError):
        return None
    if state is None or state.get("state") not in ("0", "1"):
        return None
    return {"enabled": state.get("state") == "1"}


def defender_exclusions():
    """{"paths", "extensions", "processes"} Microsoft Defender does not scan, its own settings and policies together.
    None when they cannot be read: only administrators may."""
    found = {"paths": [], "extensions": [], "processes": []}
    for root in (r"SOFTWARE\Microsoft\Windows Defender\Exclusions",
                 r"SOFTWARE\Policies\Microsoft\Windows Defender\Exclusions"):
        for kind, sub in (("paths", "Paths"), ("extensions", "Extensions"), ("processes", "Processes")):
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, rf"{root}\{sub}", 0,
                                    winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as key:
                    found[kind] += [winreg.EnumValue(key, i)[0] for i in range(winreg.QueryInfoKey(key)[1])]
            except PermissionError:
                return None
            except OSError:
                continue  # nothing excluded this way
    return {kind: list(dict.fromkeys(names)) for kind, names in found.items()}


def broad_exclusion(kind, value):
    """Whether an exclusion leaves out what Microsoft names as never to exclude: whole drives, the system, user and
    temporary folders, everything of a common file type, or the programs scripts run in."""
    value = os.path.expandvars((value or "").strip()).lower().rstrip("\\")
    if not value or value in ("*", "*.*"):
        return True
    if kind == "extensions":
        return value.lstrip("*.").lstrip(".") in BROAD_EXTENSIONS
    if kind == "processes":
        return os.path.basename(value) in BROAD_PROCESSES
    if re.fullmatch(r"[a-z]:(\\\*)?", value):
        return True
    folders = {os.path.normcase(os.path.expandvars(folder)).rstrip("\\") for folder in BROAD_FOLDERS}
    return os.path.normcase(value) in folders


def browser_policies():
    """Browser settings forced by policies: extensions installed by force, the start page, the search engine and
    the proxy ("Managed by your organization"). Adware sets these so that the user cannot change them back."""
    found = []
    for hive, hive_name in ((winreg.HKEY_LOCAL_MACHINE, "HKLM"), (winreg.HKEY_CURRENT_USER, "HKCU")):
        for browser, path in BROWSER_POLICY_KEYS:
            values = dict(_values(hive, path))
            ids = [str(data).split(";")[0] for _, data in _values(hive, path + r"\ExtensionInstallForcelist")]
            settings = values.get("ExtensionSettings")
            if isinstance(settings, str):
                try:
                    parsed = json.loads(settings)
                except ValueError:
                    parsed = {}
                ids += [ext for ext, rules in (parsed.items() if isinstance(parsed, dict) else [])
                        if isinstance(rules, dict) and rules.get("installation_mode") in ("force_installed",
                                                                                            "normal_installed")]
            if ids:
                found.append({"browser": browser, "kind": "extensions", "value": ", ".join(dict.fromkeys(ids))})
            startup = [str(data) for _, data in _values(hive, path + r"\RestoreOnStartupURLs")]
            for kind, value in (("homepage", values.get("HomepageLocation")),
                                ("newtab", values.get("NewTabPageLocation")),
                                ("search", values.get("DefaultSearchProviderSearchURL")
                                 if values.get("DefaultSearchProviderEnabled") != 0 else None),
                                ("startup", ", ".join(startup) if startup and values.get("RestoreOnStartup") == 4
                                 else None),
                                ("proxy", values.get("ProxyServer") or values.get("ProxyPacUrl"))):
                if isinstance(value, str) and value.strip():
                    found.append({"browser": browser, "kind": kind, "value": value.strip()})
    found += firefox_policies()
    return [dict(f, value=f["value"][:120]) for f in found]


def firefox_policies():
    """The same for Firefox, whose policies are a policies.json file next to it or a registry key."""
    found = []
    for folder in ("%ProgramFiles%", "%ProgramFiles(x86)%"):
        path = os.path.join(os.path.expandvars(folder), "Mozilla Firefox", "distribution", "policies.json")
        try:
            with open(path, encoding="utf-8") as f:
                policies = json.load(f).get("policies") or {}
        except (OSError, ValueError, AttributeError):
            continue
        if not isinstance(policies, dict):
            continue
        settings = policies.get("ExtensionSettings") if isinstance(policies.get("ExtensionSettings"), dict) else {}
        ids = [ext for ext, rules in settings.items()
               if isinstance(rules, dict) and rules.get("installation_mode") in ("force_installed", "normal_installed")]
        install = (policies.get("Extensions") or {}).get("Install") if isinstance(policies.get("Extensions"), dict) \
            else None
        ids += [str(item) for item in install or []]
        if ids:
            found.append({"browser": "Firefox", "kind": "extensions", "value": ", ".join(ids)})
        homepage = policies.get("Homepage") if isinstance(policies.get("Homepage"), dict) else {}
        if isinstance(homepage.get("URL"), str) and homepage["URL"].strip():
            found.append({"browser": "Firefox", "kind": "homepage", "value": homepage["URL"].strip()})
        engines = policies.get("SearchEngines") if isinstance(policies.get("SearchEngines"), dict) else {}
        if isinstance(engines.get("Default"), str) and engines["Default"].strip():
            found.append({"browser": "Firefox", "kind": "search", "value": engines["Default"].strip()})
    return found


class _Blob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_ubyte))]


class _CtlEntry(ctypes.Structure):
    _fields_ = [("SubjectIdentifier", _Blob), ("cAttribute", wintypes.DWORD), ("rgAttribute", ctypes.c_void_p)]


class _CtlUsage(ctypes.Structure):  # CTL_USAGE: nested, so that it is aligned as in C
    _fields_ = [("cUsageIdentifier", wintypes.DWORD), ("rgpszUsageIdentifier", ctypes.c_void_p)]


class _AlgorithmId(ctypes.Structure):  # CRYPT_ALGORITHM_IDENTIFIER
    _fields_ = [("pszObjId", ctypes.c_char_p), ("Parameters", _Blob)]


class _CtlInfo(ctypes.Structure):  # CTL_INFO
    _fields_ = [("dwVersion", wintypes.DWORD), ("SubjectUsage", _CtlUsage), ("ListIdentifier", _Blob),
                ("SequenceNumber", _Blob), ("ThisUpdate", wintypes.FILETIME), ("NextUpdate", wintypes.FILETIME),
                ("SubjectAlgorithm", _AlgorithmId), ("cCTLEntry", wintypes.DWORD),
                ("rgCTLEntry", ctypes.POINTER(_CtlEntry)), ("cExtension", wintypes.DWORD),
                ("rgExtension", ctypes.c_void_p)]


class _CtlContext(ctypes.Structure):  # CTL_CONTEXT
    _fields_ = [("dwMsgAndCertEncodingType", wintypes.DWORD), ("pbCtlEncoded", ctypes.c_void_p),
                ("cbCtlEncoded", wintypes.DWORD), ("pCtlInfo", ctypes.POINTER(_CtlInfo)),
                ("hCertStore", ctypes.c_void_p), ("hCryptMsg", ctypes.c_void_p), ("pbCtlContent", ctypes.c_void_p),
                ("cbCtlContent", wintypes.DWORD)]


ENCODING = 0x10001  # X509_ASN_ENCODING | PKCS_7_ASN_ENCODING


def trusted_roots():
    """SHA-1 thumbprints of the root certificates Microsoft's root program trusts: the list (a CTL) Windows keeps
    in the registry and updates itself. None when it is missing, as on a PC that never updated it."""
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\SystemCertificates\AuthRoot\AutoUpdate") as key:
            encoded = winreg.QueryValueEx(key, "EncodedCtl")[0]
    except OSError:
        return None
    crypt32 = ctypes.WinDLL("crypt32")
    crypt32.CertCreateCTLContext.restype = ctypes.POINTER(_CtlContext)
    crypt32.CertCreateCTLContext.argtypes = [wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
    crypt32.CertFreeCTLContext.argtypes = [ctypes.POINTER(_CtlContext)]
    buffer = ctypes.create_string_buffer(encoded, len(encoded))
    context = crypt32.CertCreateCTLContext(ENCODING, buffer, len(encoded))
    if not context:
        return None
    try:
        info = context.contents.pCtlInfo.contents
        thumbprints = set()
        for i in range(info.cCTLEntry):
            entry = info.rgCTLEntry[i].SubjectIdentifier
            thumbprints.add(bytes(entry.pbData[:entry.cbData]).hex().upper())
        return thumbprints
    finally:
        crypt32.CertFreeCTLContext(context)


def certificate_name(blob):
    """The display name of a certificate kept in the registry: its "Blob" is a list of properties (id, reserved,
    length, data) and the certificate itself is property 32."""
    position = 0
    while position + 12 <= len(blob):
        prop, _, length = struct.unpack_from("<III", blob, position)
        data = blob[position + 12:position + 12 + length]
        position += 12 + length
        if prop != 32:
            continue
        crypt32 = ctypes.WinDLL("crypt32")
        crypt32.CertCreateCertificateContext.restype = ctypes.c_void_p
        crypt32.CertCreateCertificateContext.argtypes = [wintypes.DWORD, ctypes.c_char_p, wintypes.DWORD]
        crypt32.CertGetNameStringW.argtypes = [ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
                                               ctypes.c_wchar_p, wintypes.DWORD]
        crypt32.CertFreeCertificateContext.argtypes = [ctypes.c_void_p]
        context = crypt32.CertCreateCertificateContext(ENCODING, data, len(data))
        if not context:
            return None
        try:
            name = ctypes.create_unicode_buffer(256)
            crypt32.CertGetNameStringW(context, 4, 0, None, name, 256)  # CERT_NAME_SIMPLE_DISPLAY_TYPE
            return name.value or None
        finally:
            crypt32.CertFreeCertificateContext(context)
    return None


def added_roots():
    """Root certificates added to this PC beyond Microsoft's root program: [{"name", "user"}]. Antivirus HTTPS
    scanning, AdGuard, Fiddler and developers' own certificates are legitimate; a root nobody knows about lets a
    program read encrypted traffic (Superfish). None when Microsoft's list is not on this PC."""
    trusted = trusted_roots()
    if trusted is None:
        return None
    found = []
    for hive, path, user in ((winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\SystemCertificates\ROOT\Certificates",
                              False),
                             (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Policies\Microsoft\SystemCertificates\Root"
                                                         r"\Certificates", False),
                             (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\SystemCertificates\Root\Certificates",
                              True)):
        try:
            root = winreg.OpenKey(hive, path)
        except OSError:
            continue
        with root:
            for thumbprint in programs._subkeys(root):
                if thumbprint.upper() in trusted or thumbprint.upper() in WINDOWS_ROOTS:
                    continue
                try:
                    with winreg.OpenKey(root, thumbprint) as key:
                        name = certificate_name(winreg.QueryValueEx(key, "Blob")[0])
                except OSError:
                    name = None
                if name and "microsoft" in name.lower():
                    continue  # roots Windows itself ships outside the program, for old signatures
                found.append({"name": name or thumbprint, "user": user})
    return found


def _value_exists(path, name):
    """Whether a registry value exists, without reading it (a stored password stays unread)."""
    hive, _, sub = path.partition("\\")
    hkey = {"HKLM": winreg.HKEY_LOCAL_MACHINE, "HKCU": winreg.HKEY_CURRENT_USER}[hive]
    size = wintypes.DWORD()
    advapi32 = ctypes.WinDLL("advapi32")
    advapi32.RegGetValueW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
                                      ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(wintypes.DWORD)]
    # RRF_RT_ANY | RRF_SUBKEY_WOW6464KEY, no buffer: only the size comes back
    return advapi32.RegGetValueW(ctypes.c_void_p(hkey), sub, name, 0x0000FFFF | 0x00010000, None, None,
                                 ctypes.byref(size)) == 0


def account_settings():
    """Accounts hidden from the sign-in screen and a password for automatic sign-in kept in plain text."""
    hidden = [name for name, data in _values(winreg.HKEY_LOCAL_MACHINE,
                                                    r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon"
                                                    r"\SpecialAccounts\UserList") if data == 0]
    winlogon = r"HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon"
    return {"hidden": hidden,
            "autologon_password": str(_read(winlogon, "AutoAdminLogon") or "") == "1" and
            _value_exists(winlogon, "DefaultPassword")}


def remote_desktop():
    """Remote Desktop: whether it accepts connections, whether it asks for credentials first (Network Level
    Authentication), and whether its service runs another library than Windows' own (RDP Wrapper)."""
    server = r"HKLM\SYSTEM\CurrentControlSet\Control\Terminal Server"
    library = _read(r"HKLM\SYSTEM\CurrentControlSet\Services\TermService\Parameters", "ServiceDll")
    return {"on": _read(server, "fDenyTSConnections") == 0,
            "nla_off": _read(server + r"\WinStations\RDP-Tcp", "UserAuthentication") == 0,
            "wrapper": isinstance(library, str) and library.strip() != "" and
            os.path.basename(os.path.expandvars(library)).lower() != "termsrv.dll"}


# One PowerShell run for what has no simple Windows call: drives' health, devices with problems, antivirus, the
# processor and memory modules, network adapters, battery wear and the event logs. Each part fails on its own and is
# then missing. Logs that can fill up with one kind of event are read on their own, so a flood of one does not push
# the others out; drive events are filtered with XPath, which does not fail on a driver this PC does not have
# --- Crash reports in files, live kernel dumps, blue screen dumps, servicing logs, installed programs ---

def _steam_folder():
    found = _read(r"HKCU\Software\Valve\Steam", "SteamPath")
    if isinstance(found, str) and found:
        return os.path.normpath(found)
    return os.path.expandvars(r"%ProgramFiles(x86)%\Steam")


def _expand(pattern):
    return os.path.expandvars(pattern.replace("%STEAM%", _steam_folder()))


def _stamps(pattern):
    """[(modification time, size)] of what matches a pattern; * may stand in any segment."""
    found = []
    for path in glob.glob(pattern):
        try:
            st = os.stat(path)
        except OSError:
            continue
        found.append((datetime.datetime.fromtimestamp(st.st_mtime), st.st_size))
    return found


def _tally(found, name, kind, folder, stamps, since):
    entry = found.setdefault((name, kind), {"name": name, "kind": kind, "folder": folder, "recent": 0, "total": 0,
                                           "newest": None, "size": 0})
    for moment, size in stamps:
        entry["total"] += 1
        entry["size"] += size
        entry["recent"] += moment >= since
        if entry["newest"] is None or moment > entry["newest"]:
            entry["newest"] = moment


def crash_files(now=None):
    """Crash reports programs keep themselves, and the reports of Windows Error Reporting on disk:
    [{"name", "kind", "folder", "recent", "total", "newest", "size"}], one per program that has a report folder."""
    since = (now or datetime.datetime.now()) - datetime.timedelta(days=CRASH_FILE_DAYS)
    found = {}
    for name, pattern in CRASH_LOCATIONS:
        full = _expand(pattern)
        folder = full.rsplit("\\", 1)[0]
        stamps = _stamps(full)
        if not stamps and not glob.glob(folder):
            continue  # the program is not on this PC
        kind = "crashpad" if "crashpad" in pattern.lower() or "minidumps" in pattern.lower() else "folder"
        _tally(found, name, kind, folder.split("*")[0].rstrip("\\"), stamps, since)
    for queue in WER_QUEUES:
        folder = os.path.expandvars(queue)
        try:
            with os.scandir(folder) as it:
                reports = list(it)
        except OSError:
            continue
        for report in reports:
            kind, _, rest = report.name.partition("_")
            program = rest.split("_")[0]
            if kind not in WER_KINDS or not program:
                continue
            try:
                moment = datetime.datetime.fromtimestamp(report.stat(follow_symlinks=False).st_mtime)
            except OSError:
                continue
            _tally(found, program, "wer", folder, [(moment, 0)], since)
    return list(found.values())


def local_dumps():
    """Windows Error Reporting's local dumps: whether the LocalDumps key is there (its presence turns them on) and
    the dumps found: [{"name": program, "time", "size", "folder"}]."""
    custom = _read(LOCAL_DUMPS_KEY, "DumpFolder")
    folders = [os.path.expandvars(f) for f in ([custom] if isinstance(custom, str) and custom else []) + LOCAL_DUMP_FOLDERS]
    dumps, seen = [], set()
    for folder in folders:
        if os.path.normcase(folder) in seen:
            continue
        seen.add(os.path.normcase(folder))
        for path in glob.glob(os.path.join(folder, "*.dmp")):
            try:
                st = os.stat(path)
            except OSError:
                continue
            stem = os.path.basename(path)[:-4]
            name, _, pid = stem.rpartition(".")
            dumps.append({"name": name if name and pid.isdigit() else stem,
                          "time": datetime.datetime.fromtimestamp(st.st_mtime), "size": st.st_size, "folder": folder})
    return {"enabled": engine.key_exists(LOCAL_DUMPS_KEY), "folder": folders[0], "dumps": dumps}


def live_kernel():
    """Live kernel dumps: Windows recovered from a hung driver without a blue screen. The folder is readable only
    by administrators; the registry keeps the names of the components that ever produced one."""
    root = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "LiveKernelReports")
    components = sorted({name for key in ("LiveKernelReports", "FullLiveKernelReports")
                         for name in _subkeys(winreg.HKEY_LOCAL_MACHINE, rf"SYSTEM\CurrentControlSet\Control\CrashControl\{key}")})
    dumps, readable = [], True
    try:
        with os.scandir(root) as it:
            top = list(it)
    except PermissionError:
        readable, top = False, []
    except OSError:
        top = []  # no folder: no live dump was ever written
    for entry in top:
        try:
            if entry.is_dir(follow_symlinks=False):
                dumps += [{"component": entry.name, "time": moment, "size": size}
                          for moment, size in _stamps(os.path.join(entry.path, "*.dmp"))]
            elif entry.name.lower().endswith(".dmp"):
                st = entry.stat(follow_symlinks=False)
                dumps.append({"component": "", "time": datetime.datetime.fromtimestamp(st.st_mtime), "size": st.st_size})
        except OSError:
            continue
    return {"readable": readable, "dumps": dumps, "components": components}


def _filetime_moment(value):
    """A FILETIME from the registry (a number or eight bytes) as a local date and time, or None."""
    if isinstance(value, bytes):
        value = int.from_bytes(value[:8], "little") if len(value) >= 8 else 0
    if not isinstance(value, int) or value <= 116444736000000000:
        return None
    try:
        return datetime.datetime.fromtimestamp((value - 116444736000000000) / 10_000_000)
    except (OverflowError, OSError, ValueError):
        return None


def kernel_dumps():
    """Blue screen dumps and their settings: the dates of the minidumps, MEMORY.DMP, and CrashControl."""
    folder = os.path.expandvars(_read(CRASH_CONTROL, "MinidumpDir") or r"%SystemRoot%\Minidump")
    dump_file = os.path.expandvars(_read(CRASH_CONTROL, "DumpFile") or r"%SystemRoot%\MEMORY.DMP")
    readable = True
    try:
        os.listdir(folder)
    except PermissionError:
        readable = False
    except OSError:
        pass
    minidumps = sorted((moment for moment, _ in _stamps(os.path.join(folder, "*.dmp"))), reverse=True)
    memory = None
    try:
        st = os.stat(dump_file)
        memory = {"time": datetime.datetime.fromtimestamp(st.st_mtime), "size": st.st_size}
    except OSError:
        pass
    return {"readable": readable, "minidumps": minidumps, "memory_dmp": memory,
            "enabled": _read(CRASH_CONTROL, "CrashDumpEnabled"), "last_crash": _filetime_moment(_read(CRASH_CONTROL, "LastCrashTime")),
            "count": _read(CRASH_CONTROL, "MinidumpsCount")}


def cbs_logs():
    """The largest servicing log and the cab_* files it leaves in Windows\\Temp when it cannot compress itself."""
    root = os.environ.get("SystemRoot", r"C:\Windows")
    largest = None
    try:
        with os.scandir(os.path.join(root, "Logs", "CBS")) as it:
            for entry in it:
                try:
                    if entry.is_file(follow_symlinks=False):
                        size = entry.stat(follow_symlinks=False).st_size
                        if largest is None or size > largest["size"]:
                            largest = {"name": entry.name, "size": size}
                except OSError:
                    continue
    except OSError:
        pass
    cabs = None
    try:
        with os.scandir(os.path.join(root, "Temp")) as it:
            cabs = sum(1 for entry in it if entry.name.lower().startswith("cab_"))
    except OSError:
        pass  # a standard user may create files in Windows\Temp but not list it
    return {"largest": largest, "cabs": cabs}


def software():
    """What the check of programs with documented problems looks at: installed programs (lower-case title ->
    (title, version)), the Store packages and services of interest, and RivaTuner's version."""
    found = {}
    for hive, path in programs.UNINSTALL:
        try:
            root = winreg.OpenKey(hive, path)
        except OSError:
            continue
        with root:
            for subkey in programs._subkeys(root):
                try:
                    with winreg.OpenKey(root, subkey) as key:
                        title, version, system = programs._values(key, "DisplayName", "DisplayVersion", "SystemComponent")
                except OSError:
                    continue
                if isinstance(title, str) and title.strip() and system != 1:
                    found.setdefault(title.strip().lower(), (title.strip(), str(version or "")))
    packages = []
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, programs.PACKAGES) as key:
            packages = [name for name in programs._subkeys(key) if WATCHED_PACKAGES.search(name)]
    except OSError:
        pass
    watched = {}
    for name in _subkeys(winreg.HKEY_LOCAL_MACHINE, SERVICES_KEY):
        display = _read(rf"HKLM\{SERVICES_KEY}\{name}", "DisplayName")
        display = display if isinstance(display, str) and not display.startswith("@") else name
        if WATCHED_SERVICES.search(f"{name} {display}"):
            watched[name.lower()] = {"display": display, "start": _read(rf"HKLM\{SERVICES_KEY}\{name}", "Start")}
    return {"programs": found, "packages": packages, "services": watched,
            "rtss": file_version(os.path.expandvars(RTSS_PATH))}


POWERSHELL_SCRIPT = r"""
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object Text.UTF8Encoding $false
$r = @{}
function Pick($found) {
  return ,@($found | ForEach-Object {
    $p = $_.Properties
    # The first values, or for a low memory warning the three programs that took most and the top kernel pool tag
    $take = if ($_.Id -eq 2004 -and $_.ProviderName -like '*Resource-Exhaustion*') { 20, 27, 34, 14 } else { 0..8 }
    @{ id = $_.Id; provider = $_.ProviderName; level = [int]$_.Level; time = $_.TimeCreated.ToString('s');
       args = @($take | ForEach-Object { if ($_ -lt $p.Count) { [string]$p[$_].Value } else { '' } }) } })
}
function Events($filter, $max = 500) {
  try { $found = Get-WinEvent -FilterHashtable $filter -MaxEvents $max -ErrorAction Stop }
  catch { if ($_.FullyQualifiedErrorId -like 'NoMatchingEventsFound*') { return ,@() } throw }
  return Pick $found
}
function EventsFrom($log, $providers, $levels, $days, $max = 500) {
  $from = ($providers | ForEach-Object { 'Provider[@Name=''' + $_ + ''']' }) -join ' or '
  $level = ($levels | ForEach-Object { 'Level=' + $_ }) -join ' or '
  $xpath = '*[System[(' + $from + ') and (' + $level + ') and TimeCreated[timediff(@SystemTime) <= ' +
    ([int64]$days * 86400000) + ']]]'
  try { $found = Get-WinEvent -LogName $log -FilterXPath $xpath -MaxEvents $max -ErrorAction Stop }
  catch { if ($_.FullyQualifiedErrorId -like 'NoMatchingEventsFound*') { return ,@() } throw }
  return Pick $found
}
# The storage classes straight from CIM: Get-PhysicalDisk first loads its module, which takes half a second
$media = @{ 0 = 'Unspecified'; 3 = 'HDD'; 4 = 'SSD'; 5 = 'SCM' }
$health = @{ 0 = 'Healthy'; 1 = 'Warning'; 2 = 'Unhealthy'; 5 = 'Unknown' }
$bus = @{ 1 = 'SCSI'; 3 = 'ATA'; 7 = 'USB'; 8 = 'RAID'; 10 = 'SAS'; 11 = 'SATA'; 12 = 'SD'; 13 = 'MMC';
          14 = 'Virtual'; 16 = 'Storage Spaces'; 17 = 'NVMe'; 19 = 'UFS' }
try { $found = @(Get-CimInstance -Namespace root/Microsoft/Windows/Storage -ClassName MSFT_PhysicalDisk)
  $r.disks = @($found | ForEach-Object { @{ id = [string]$_.DeviceId; name = [string]$_.FriendlyName;
    media = [string]$media[[int]$_.MediaType]; health = [string]$health[[int]$_.HealthStatus];
    bus = [string]$bus[[int]$_.BusType] } })
  # Wear and read errors: only administrators may read them
  try { $r.wear = @($found | ForEach-Object { $c = Get-CimAssociatedInstance -InputObject $_ -ResultClassName MSFT_StorageReliabilityCounter
    @{ id = [string]$_.DeviceId; wear = $c.Wear; read_errors = $c.ReadErrorsUncorrected } }) } catch {}
} catch {}
try { $g = Get-CimInstance -Namespace root/Microsoft/Windows/DeviceGuard -ClassName Win32_DeviceGuard
  $r.vbs = @{ available = @($g.AvailableSecurityProperties | ForEach-Object { [int]$_ });
              running = @($g.SecurityServicesRunning | ForEach-Object { [int]$_ }) } } catch {}
try { $r.video = @(Get-CimInstance Win32_VideoController | ForEach-Object { @{ name = [string]$_.Name;
  inf = [string]$_.InfFilename; version = [string]$_.DriverVersion; pnp = [string]$_.PNPDeviceID;
  code = [int]$_.ConfigManagerErrorCode;
  date = $(if ($_.DriverDate) { $_.DriverDate.ToString('s') } else { '' }) } }) } catch {}
try { $r.devices = @(Get-CimInstance Win32_PnPEntity -Filter 'ConfigManagerErrorCode <> 0' | ForEach-Object {
  @{ name = [string]$_.Name; code = [int]$_.ConfigManagerErrorCode; cls = [string]$_.PNPClass;
     pnp = [string]$_.PNPDeviceID } }) } catch {}
# Only these two: asked for everything, Win32_Processor first measures the load for a second
try { $c = @(Get-CimInstance -Query 'SELECT NumberOfLogicalProcessors, ThreadCount FROM Win32_Processor')
  $r.cpu_threads = [int]($c | Measure-Object -Property NumberOfLogicalProcessors -Sum).Sum
  $r.cpu_hardware_threads = [int]($c | Measure-Object -Property ThreadCount -Sum).Sum } catch {}
try { $r.modules = @(Get-CimInstance Win32_PhysicalMemory | ForEach-Object { @{ size = [long]$_.Capacity;
  speed = [int]$_.Speed; configured = [int]$_.ConfiguredClockSpeed; part = ([string]$_.PartNumber).Trim();
  maker = ([string]$_.Manufacturer).Trim(); form = [int]$_.FormFactor; slot = [string]$_.DeviceLocator } }) } catch {}
try { $r.antivirus = @(Get-CimInstance -Namespace root/SecurityCenter2 -ClassName AntiVirusProduct | ForEach-Object {
  @{ name = [string]$_.displayName; state = [int]$_.productState } }) } catch {}
try { $r.adapters = @(Get-CimInstance -Namespace root/StandardCimv2 -ClassName MSFT_NetAdapter |
  Where-Object { $_.ConnectorPresent -and $_.MediaConnectState -eq 1 -and $_.NdisPhysicalMedium -eq 14 } |
  ForEach-Object { @{ name = [string]$_.InterfaceDescription; speed = [long]$_.Speed } }) } catch {}
try {
  $last = (New-Object -ComObject Microsoft.Update.AutoUpdate).Results.LastInstallationSuccessDate
  if ($last -and $last.Year -gt 2000) { $r.last_update = $last.ToString('s') }
} catch {}
try {
  $design = @(Get-CimInstance -Namespace root/wmi -ClassName BatteryStaticData | ForEach-Object { [long]$_.DesignedCapacity })
  $full = @(Get-CimInstance -Namespace root/wmi -ClassName BatteryFullChargedCapacity |
    ForEach-Object { [long]$_.FullChargedCapacity })
  $r.battery = @{ design = $design; full = $full }
} catch {}
try { $r.image = [string](Repair-WindowsImage -Online -CheckHealth).ImageHealthState } catch {}
try { $d = Get-CimInstance -Namespace root/Microsoft/Windows/Defender -ClassName MSFT_MpComputerStatus
  $r.defender = @{ mode = [string]$d.AMRunningMode; realtime = [bool]$d.RealTimeProtectionEnabled;
                   tamper = [bool]$d.IsTamperProtected } } catch {}
# Certificates marked as untrusted: malware puts antivirus makers' there so their programs cannot start
try { $r.disallowed = @(Get-ChildItem Cert:/LocalMachine/Disallowed, Cert:/CurrentUser/Disallowed |
  ForEach-Object { [string]$_.Subject }) } catch {}
try { $r.teredo = [int](@(Get-CimInstance -Namespace root/StandardCimv2 -ClassName MSFT_NetTeredoConfiguration)[0].Type)
} catch {}
# WMI answers, or the error it gives (a damaged repository or provider)
try { $null = Get-WmiObject -Class Win32_OperatingSystem -ErrorAction Stop; $r.wmi = 0 }
catch { $code = $_.Exception.ErrorCode; if (-not $code) { $code = $_.Exception.HResult }
  $r.wmi = [int64]$code -band 0xFFFFFFFF; if (-not $r.wmi) { $r.wmi = 1 } }
try { $r.disk_paths = @(Get-CimInstance -Namespace root/Microsoft/Windows/Storage -ClassName MSFT_Disk |
  ForEach-Object { @{ number = [int]$_.Number; path = [string]$_.Path } }) } catch {}
try { $r.volumes = @(Get-CimInstance -Namespace root/Microsoft/Windows/Storage -ClassName MSFT_Volume |
  Where-Object { $_.DriveLetter } | ForEach-Object { @{ drive = [string]$_.DriveLetter; health = [int]$_.HealthStatus } })
} catch {}
try { $r.dirty = @(Get-CimInstance -Query 'SELECT DriveLetter, DirtyBitSet FROM Win32_Volume WHERE DriveLetter IS NOT NULL' |
  Where-Object { $_.DirtyBitSet } | ForEach-Object { [string]$_.DriveLetter }) } catch {}
try { $r.cycles = @(Get-CimInstance -Namespace root/wmi -ClassName BatteryCycleCount |
  ForEach-Object { [int]$_.CycleCount }) } catch {}
# What slowed the last starts and shutdowns, and the desktop short of video memory, as Windows measured it itself.
# Only administrators may read this log
$keep = 'BootTime', 'MainPathBootTime', 'BootPostBootTime', 'BootIsRebootAfterInstall', 'Name', 'FriendlyName', 'Path',
  'TotalTime', 'DegradationTime', 'ShutdownTime', 'Scenario', 'DisplayDeviceFriendlyName', 'MemorySize'
try {
  $xpath = '*[System[((EventID>=100 and EventID<=110) or (EventID>=200 and EventID<=203) or EventID=500 or ' +
    'EventID=501) and TimeCreated[timediff(@SystemTime) <= ' + ([int64]%(perf_days)d * 86400000) + ']]]'
  $found = @(Get-WinEvent -LogName 'Microsoft-Windows-Diagnostics-Performance/Operational' -FilterXPath $xpath `
    -MaxEvents 400 -ErrorAction Stop)
  $r.perf_events = @($found | ForEach-Object { $data = @{}
    foreach ($item in ([xml]$_.ToXml()).Event.EventData.Data) {
      if ($keep -contains $item.Name) { $data[$item.Name] = [string]$item.'#text' } }
    @{ id = $_.Id; time = $_.TimeCreated.ToString('s'); data = $data } })
} catch { if ($_.FullyQualifiedErrorId -like 'NoMatchingEventsFound*') { $r.perf_events = @() } }
# Threats Microsoft Defender found and that are still there
try { $r.threats = @(Get-CimInstance -Namespace root/Microsoft/Windows/Defender -ClassName MSFT_MpThreat |
  Where-Object { $_.IsActive } | ForEach-Object { @{ name = [string]$_.ThreatName; severity = [int]$_.SeverityID } })
} catch {}
# The firewall as Windows applies it (policies included), for the domain, private and public networks
try { $fw = New-Object -ComObject HNetCfg.FwPolicy2
  $r.firewall = @{ domain = [bool]$fw.FirewallEnabled(1); private = [bool]$fw.FirewallEnabled(2);
                   public = [bool]$fw.FirewallEnabled(4) } } catch {}
try { $r.firewall_products = @(Get-CimInstance -Namespace root/SecurityCenter2 -ClassName FirewallProduct |
  ForEach-Object { [string]$_.displayName }) } catch {}
try { $r.smb1 = @(Get-CimInstance -ClassName Win32_OptionalFeature -Filter 'Name LIKE ''SMB1Protocol%%''' |
  Where-Object { $_.InstallState -eq 1 } | ForEach-Object { [string]$_.Name }) } catch {}
try { $r.local_users = @(Get-LocalUser | ForEach-Object { @{ name = [string]$_.Name; enabled = [bool]$_.Enabled;
  sid = [string]$_.SID.Value } }) } catch {}
# BitLocker on the Windows drive: encrypted or not, protected or not, and the IDs of its recovery passwords
try { $v = @(Get-CimInstance -Namespace root/cimv2/Security/MicrosoftVolumeEncryption -ClassName Win32_EncryptableVolume `
    -Filter ('DriveLetter=''' + $env:SystemDrive + ''''))
  if ($v.Count) { $keys = Invoke-CimMethod -InputObject $v[0] -MethodName GetKeyProtectors -Arguments @{ KeyProtectorType = [uint32]3 }
    $r.bitlocker = @{ conversion = [int]$v[0].ConversionStatus; protection = [int]$v[0].ProtectionStatus;
                      recovery = @($keys.VolumeKeyProtectorID | ForEach-Object { [string]$_ }) } }
} catch {}
try { $r.time_events = Events @{ LogName = 'System'; ProviderName = 'Microsoft-Windows-Time-Service'; Id = 35, 36, 37;
  StartTime = (Get-Date).AddDays(-%(time_days)d) } } catch {}
$since = (Get-Date).AddDays(-%(event_days)d)
try { $r.events = Events @{ LogName = 'System'; StartTime = $since; Level = 1, 2, 3;
  Id = 41, 1001, 2004, 4101, 4199, 6008 } } catch {}
try { $r.disk_events = EventsFrom 'System' @('%(disk_providers)s') @(1, 2, 3) %(event_days)d } catch {}
try { $r.nvidia_events = EventsFrom 'System' @('nvlddmkm') @(1, 2) %(event_days)d } catch {}
try { $r.throttle_events = Events @{ LogName = 'System'; ProviderName = 'Microsoft-Windows-Kernel-Processor-Power';
  Id = 37; StartTime = (Get-Date).AddDays(-%(throttle_days)d) } } catch {}
try { $r.shutdowns = Events @{ LogName = 'System'; ProviderName = 'Microsoft-Windows-Kernel-General'; Id = 13;
  StartTime = (Get-Date).AddDays(-%(service_days)d) } } catch {}
try { $r.service_events = Events @{ LogName = 'System'; ProviderName = 'Service Control Manager';
  Id = 7000, 7023, 7024, 7031, 7034; StartTime = (Get-Date).AddDays(-%(service_days)d) } } catch {}
try { $r.update_events = Events @{ LogName = 'System'; ProviderName = 'Microsoft-Windows-WindowsUpdateClient';
  Id = 19, 20; StartTime = $since } } catch {}
try { $r.memory_tests = Events @{ LogName = 'System'; ProviderName = 'Microsoft-Windows-MemoryDiagnostics-Results';
  Id = 1101, 1102, 1201, 1202 } 5 } catch {}
try { $r.live_events = ,@((Events @{ LogName = 'Application'; ProviderName = 'Windows Error Reporting'; Id = 1001;
  StartTime = $since }) | Where-Object { $_.args.Count -gt 5 -and $_.args[2] -eq 'LiveKernelEvent' }) } catch {}
try { $r.whea = Events @{ LogName = 'System'; ProviderName = 'Microsoft-Windows-WHEA-Logger'; Level = 1, 2, 3;
  StartTime = $since } } catch {}
try { $r.app_events = Events @{ LogName = 'Application'; Id = 1000, 1002;
  StartTime = (Get-Date).AddDays(-%(app_days)d) } } catch {}
$r | ConvertTo-Json -Depth 5 -Compress
""" % {"event_days": EVENT_DAYS, "app_days": APP_EVENT_DAYS, "service_days": SERVICE_DAYS,
       "throttle_days": THROTTLE_DAYS, "disk_providers": "', '".join(DISK_PROVIDERS), "perf_days": PERF_DAYS,
       "time_days": TIME_DAYS}

EVENT_KEYS = ("events", "disk_events", "nvidia_events", "throttle_events", "shutdowns", "service_events",
              "update_events", "memory_tests", "live_events", "whea", "app_events", "time_events")


def _list(value):
    """PowerShell turns a list of one into the item itself and an empty list into null."""
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _event(raw):
    try:
        moment = datetime.datetime.fromisoformat(raw["time"])
    except (KeyError, TypeError, ValueError):
        return None
    return {"id": raw.get("id"), "provider": str(raw.get("provider") or ""), "level": raw.get("level"),
            "time": moment, "args": [str(a) for a in _list(raw.get("args"))]}


def start_powershell():
    # The script goes as the command itself, in plain text: it has no double quotes or backslashes to escape.
    # Not from standard input, which runs line by line as if typed at the prompt, and not base64-encoded, which
    # antivirus programs treat as suspicious
    return subprocess.Popen(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", POWERSHELL_SCRIPT],
                            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                            creationflags=engine.CREATE_NO_WINDOW, env=engine.clean_env())


def finish_powershell(process, timeout=POWERSHELL_TIMEOUT):
    """The facts the script found: only the parts it could read."""
    try:
        out, _ = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        process.communicate()
        return {}
    try:
        raw = json.loads(out.decode("utf-8", errors="replace").strip().lstrip("\ufeff") or "{}")
    except ValueError:
        return {}
    if not isinstance(raw, dict):
        return {}
    facts = {}
    for key in ("disks", "devices", "antivirus", "video", "modules", "wear", "adapters"):
        if key in raw:
            facts[key] = [item for item in _list(raw[key]) if isinstance(item, dict)]
    for key in ("cpu_threads", "cpu_hardware_threads"):
        if isinstance(raw.get(key), int) and raw[key] > 0:
            facts[key] = raw[key]
    if raw.get("last_update"):
        try:
            facts["last_update"] = datetime.datetime.fromisoformat(raw["last_update"])
        except (TypeError, ValueError):
            pass
    if isinstance(raw.get("image"), str) and raw["image"]:
        facts["image"] = raw["image"]
    battery = raw.get("battery")
    if isinstance(battery, dict):
        design, full = sum(_list(battery.get("design"))), sum(_list(battery.get("full")))
        facts["battery"] = {"design": design, "full": full} if design > 0 and full > 0 else None
    if isinstance(raw.get("vbs"), dict):
        facts["vbs"] = {key: [v for v in _list(raw["vbs"].get(key)) if isinstance(v, int)]
                        for key in ("available", "running")}
    for key in EVENT_KEYS:
        if key in raw:
            facts[key] = [e for e in (_event(item) for item in _list(raw[key]) if isinstance(item, dict)) if e]
    defender = raw.get("defender")
    if isinstance(defender, dict) and defender.get("mode"):
        facts["defender"] = {"mode": str(defender["mode"]), "realtime": bool(defender.get("realtime")),
                             "tamper": bool(defender.get("tamper"))}
    for key in ("disallowed", "dirty"):
        if key in raw:
            facts[key] = [str(item) for item in _list(raw[key]) if item]
    for key in ("teredo", "wmi"):
        if isinstance(raw.get(key), int):
            facts[key] = raw[key]
    for key in ("disk_paths", "volumes"):
        if key in raw:
            facts[key] = [item for item in _list(raw[key]) if isinstance(item, dict)]
    for key in ("threats", "local_users"):
        if key in raw:
            facts[key] = [item for item in _list(raw[key]) if isinstance(item, dict)]
    for key in ("firewall_products", "smb1"):
        if key in raw:
            facts[key] = [str(item) for item in _list(raw[key]) if item]
    if isinstance(raw.get("firewall"), dict):
        facts["firewall"] = {key: bool(raw["firewall"].get(key)) for key in ("domain", "private", "public")}
    if isinstance(raw.get("bitlocker"), dict):
        locker = raw["bitlocker"]
        facts["bitlocker"] = {"conversion": locker.get("conversion"), "protection": locker.get("protection"),
                              "recovery": [str(k) for k in _list(locker.get("recovery")) if k]}
    cycles = [c for c in _list(raw.get("cycles")) if isinstance(c, int) and c > 0]
    if cycles:
        facts["battery_cycles"] = max(cycles)
    if "perf_events" in raw:
        found = []
        for item in _list(raw["perf_events"]):
            if not isinstance(item, dict):
                continue
            try:
                moment = datetime.datetime.fromisoformat(item.get("time") or "")
            except (TypeError, ValueError):
                continue
            data = item.get("data") if isinstance(item.get("data"), dict) else {}
            found.append({"id": item.get("id"), "time": moment, "data": {k: str(v) for k, v in data.items()}})
        facts["perf_events"] = found
    return facts


def gather(report=lambda step: None, api=None):
    """Reads everything the checks need. report(group) is called as each group of checks is ready."""
    api = api or limiter.WindowsApi()
    facts = {"now": datetime.datetime.now()}

    def read(name, function, *args):
        try:
            facts[name] = function(*args)
        except Exception:  # one fact that cannot be read must not stop the others
            pass

    read("memory", memory)
    read("pagefile", pagefile)
    read("top_memory", programs_by_memory, api)
    read("processes", lambda: {name for _, name in api.processes()})
    # The processor is measured before PowerShell starts, which would take a share of it itself
    read("cpu", cpu, api)
    # PowerShell then runs while the checks below take their time
    try:
        process = start_powershell()
    except OSError:
        process = None
    read("admin", engine.is_admin)
    read("pool", kernel_pool)
    read("processor", processor)
    read("model", sysinfo.model)
    read("power", power)
    read("displays", displays)
    read("vram", video_memory)
    read("gpu_preferences", gpu_preferences)
    read("startup", startup_programs)
    read("startup_impact", startup_impact)
    read("software", software)
    read("game_dvr", game_dvr)
    read("network_setup", network_setup)
    read("boot", boot_options)
    read("uptime", uptime)
    read("fast_startup", fast_startup)
    read("sleep", sleep_state)
    read("graphics", sysinfo.graphics)
    if X3D_DUAL.search((facts.get("processor") or {}).get("name", "")):
        read("x3d", x3d_support)
        read("game_bar", game_bar)
    report("performance")
    read("drives", drives)
    read("system_disk", system_disk)
    read("trim_off", trim_off)
    read("temp", lambda: temp_report(temp_dir()) if temp_dir() else None)
    read("cbs", cbs_logs)
    if process:
        try:
            facts.update(finish_powershell(process))
        except OSError:
            pass
    # The PCI Express lanes of the graphics cards, known now that PowerShell has named them, and the drives' own
    # health reports and links
    read("links", lambda: {v.get("name"): pcie_width(v["pnp"]) for v in facts.get("video") or []
                           if pci_vendor(v.get("pnp"))})
    read("drive_health", lambda: drive_health(facts.get("disks") or []))
    read("drive_links", lambda: drive_links(facts.get("disks") or [], facts.get("disk_paths") or []))
    report("storage")
    read("disabled_services", disabled_services)
    read("app_platform", app_platform)
    read("wmi_repository", wmi_repository)
    read("recovery", recovery_environment)
    read("wer_off", wer_off)
    read("crash_files", lambda: crash_files(facts["now"]))
    read("local_dumps", local_dumps)
    read("live_kernel", live_kernel)
    read("kernel_dumps", kernel_dumps)
    read("vc_runtime", vc_runtime)
    report("stability")
    read("restart_pending", restart_pending)
    read("update_settings", update_settings)
    read("windows_updated", last_windows_update)
    read("windows", windows)
    read("firmware", firmware)
    read("security", security_settings)
    read("managed", managed)
    read("blocked", blocked_tools)
    read("defender_exclusions", defender_exclusions)
    read("browser_policies", browser_policies)
    read("added_roots", added_roots)
    read("account_settings", account_settings)
    read("remote_desktop", remote_desktop)
    read("proxy", proxy)
    read("hosts", hosts)
    report("security")
    return facts


# --- Verdicts ---

def _percent(part, whole):
    return round(100 * part / whole) if whole else 0


def _days_ago(facts, days):
    return facts["now"] - datetime.timedelta(days=days)


def _desktop(facts):
    """A PC without a battery: a laptop's choices (power saving, graphics through the processor) are by design."""
    return not (facts.get("power") or {}).get("battery")


def _virtual(facts):
    return bool(VIRTUAL_MACHINES.search(facts.get("model") or ""))


def check_ram_load(facts):
    mem = facts.get("memory")
    if not mem:
        return unknown("ram_load")
    load = mem["load"]
    severity = "problem" if load >= 90 else "warning" if load >= 80 else "ok"
    items = [("item_program_size", {"name": name, "size": Size(size)})
             for name, size in facts.get("top_memory", [])[:5]]
    return Finding("ram_load", severity, "ram_high" if severity != "ok" else "ram_ok",
                   {"percent": load, "total": Size(mem["total"])}, items, ["memory", "taskmgr"])


def check_ram_size(facts):
    mem = facts.get("memory")
    if not mem:
        return unknown("ram_size")
    total = mem["total"]
    installed = sum(m.get("size") or 0 for m in facts.get("modules") or [])
    # Memory set aside for AMD's processor graphics is gone on purpose (Ryzen laptops can reserve 8-16 GB)
    graphics = sum(size for name, size in (facts.get("vram") or {}).items()
                   if _vendor_of(facts, name) == AMD and not is_discrete(AMD, name))
    params = {"total": Size(total), "installed": Size(installed)}
    # Windows reports a little less than is installed: part of it goes to the firmware. A quarter or more missing is
    # something else: a memory limit in the boot options, a BIOS setting or a module not seen
    missing = installed - total - graphics
    if installed and missing > max(1.5 * GB, installed / 4):
        return Finding("ram_size", "warning", "ram_reserved", params, actions=["system_config"])
    severity = "problem" if total < 3.5 * GB else "warning" if total < 7 * GB else "ok"
    return Finding("ram_size", severity, "ram_size_low" if severity != "ok" else "ram_size_ok", params)


def rated_speed(part):
    """The speed a memory kit is rated for (XMP/EXPO), read from its part number, or None."""
    for pattern, speed in RATED_SPEED:
        found = pattern.search(part or "")
        if found:
            return speed(found)
    return None


def check_memory_config(facts):
    modules = facts.get("modules")
    if modules is None:
        return unknown("memory_config")
    if not modules or _virtual(facts):
        return None  # a virtual machine's memory says nothing about the real modules
    total = sum(m.get("size") or 0 for m in modules)
    configured = min((m.get("configured") or 0 for m in modules), default=0)
    params = {"n": len(modules), "total": Size(total), "speed": configured}
    items = [("item_module" if m.get("configured") else "item_module_nospeed",
              {"slot": m.get("slot") or "?", "size": Size(m.get("size") or 0), "part": m.get("part") or "?",
               "speed": m.get("configured") or 0}) for m in modules]
    findings = []
    # One stick in a desktop: the processor reads memory over one channel instead of two
    if _desktop(facts) and len(modules) == 1 and modules[0].get("form") in (DIMM, SODIMM):
        findings.append(("warning", "single_module"))
    rated = max((rated_speed(m.get("part")) or 0 for m in modules), default=0)
    if rated and configured and rated - configured >= 200:
        findings.append(("info", "xmp_off"))
        params.update(rated=rated)
    kinds = {(m.get("part") or "?", m.get("size")) for m in modules}
    if len(kinds) > 1:
        findings.append(("info", "mixed_modules"))
    if not findings:
        return Finding("memory_config", "ok", "modules_ok" if configured else "modules_ok_nospeed", params, items)
    severity, line = min(findings, key=lambda item: SEVERITIES.index(item[0]))
    return Finding("memory_config", severity, line, params, items)


def check_kernel_memory(facts):
    pool, mem = facts.get("pool"), facts.get("memory")
    if not pool or not mem:
        return unknown("kernel_memory")
    used = pool["nonpaged"]
    params = {"size": Size(used)}
    # The biggest user Windows named when memory last ran low: a pool tag like "Ndis" or "ABCD"
    tags = [e["args"][3] for e in sorted(facts.get("events") or [], key=lambda e: e["time"], reverse=True)
            if e["id"] == 2004 and len(e["args"]) > 3 and e["args"][3].strip()]
    items = [("item_pool_tag", {"tag": tags[0].strip()})] if tags else []
    if used >= 4 * GB:
        return Finding("kernel_memory", "problem", "pool_leak", params, items, ["taskmgr"])
    if used >= 2 * GB or (used >= GB and used >= mem["total"] / 10):
        return Finding("kernel_memory", "warning", "pool_leak", params, items, ["taskmgr"])
    return Finding("kernel_memory", "ok", "pool_ok", params)


def check_pagefile(facts):
    mem, page = facts.get("memory"), facts.get("pagefile")
    if not mem or page is None:
        return unknown("pagefile")
    files = page["files"]
    used = _percent(mem["commit_total"] - mem["commit_avail"], mem["commit_total"])
    params = {"percent": used}
    # Windows warns in the log when memory runs out and names the three programs that took most
    since = _days_ago(facts, EVENT_DAYS)
    low = [e for e in facts.get("events") or [] if e["id"] == 2004 and "exhaustion" in e["provider"].lower()
           and e["time"] >= since]
    takers = {}
    for e in low:
        for name in e["args"][:3]:
            if name:
                takers[name] = takers.get(name, 0) + 1
    items = [("item_name", {"name": name}) for name, _ in sorted(takers.items(), key=lambda item: -item[1])[:5]]
    if used >= 90:
        return Finding("pagefile", "problem", "commit_high", params, items, ["virtual_memory", "memory"])
    if low:
        return Finding("pagefile", "warning", "low_memory", dict(params, n=len(low), days=EVENT_DAYS), items,
                       ["virtual_memory", "memory"])
    if not files:
        return Finding("pagefile", "warning", "pagefile_off", params, actions=["virtual_memory"])
    entries = [page_file_entry(line) for line in files]
    fixed = [maximum for _, _, maximum in entries if maximum > 0]
    drives = {d["drive"]: d for d in facts.get("drives") or []}
    if fixed and (sum(fixed) * MB < 4 * GB or mem["total"] + sum(fixed) * MB < 16 * GB):
        return Finding("pagefile", "warning", "pagefile_small", dict(params, size=Size(sum(fixed) * MB)),
                       actions=["virtual_memory"])
    system = next((d["drive"] for d in drives.values() if d["system"]), None)
    for drive, _, maximum in entries:
        if drive == "?:":  # "any drive": Windows puts it on its own
            drive = system
        elif drives and drive not in drives:
            return Finding("pagefile", "warning", "pagefile_drive", dict(params, drive=drive),
                           actions=["virtual_memory"])
        # A page file Windows sizes itself cannot grow on a full drive
        if maximum == 0 and drive in drives and drives[drive]["free"] < 4 * GB:
            return Finding("pagefile", "warning", "pagefile_no_room", dict(params, drive=drive),
                           actions=["virtual_memory", "storage"])
    if page.get("existing") == []:
        return Finding("pagefile", "warning", "pagefile_missing", params, actions=["virtual_memory"])
    return Finding("pagefile", "ok", "pagefile_ok", params, actions=["virtual_memory"])


def check_cpu_load(facts):
    sample = facts.get("cpu")
    if not sample:
        return unknown("cpu_load")
    load = round(sample["load"])
    items = [("item_program_percent", {"name": name, "percent": round(share)}) for name, share in sample["top"]]
    # Hardware interrupts and deferred procedure calls: a driver that keeps one processor this busy makes sound
    # crackle and games stutter, even while the total load looks low
    since_start, now = sample.get("interrupts") or 0, sample.get("interrupts_now") or 0
    storm = since_start >= INTERRUPTS_HIGH or now >= INTERRUPTS_NOW_HIGH
    if storm:
        items.insert(0, ("item_interrupts", {"percent": round(max(since_start, now))}))
    if load >= 80:
        return Finding("cpu_load", "warning", "cpu_high", {"percent": load}, items, ["taskmgr"])
    if storm:
        return Finding("cpu_load", "warning", "interrupts_high", {"percent": round(max(since_start, now))}, items,
                       ["devices"])
    return Finding("cpu_load", "ok", "cpu_ok", {"percent": load}, items, ["taskmgr"])


def check_cpu_microcode(facts):
    cpu_info = facts.get("processor")
    if not cpu_info or not RAPTOR_NAME.search(cpu_info["name"]) or cpu_info["model"] != RAPTOR_MODEL:
        return None  # only Intel's 13th and 14th Gen desktop processors of the Raptor Lake die are affected
    revision = cpu_info["microcode"]
    if revision is None:
        return unknown("cpu_microcode")
    params = {"name": cpu_info["name"], "revision": f"0x{revision:X}", "fixed": f"0x{RAPTOR_FIXED:X}",
              "latest": f"0x{RAPTOR_LATEST:X}"}
    if revision >= RAPTOR_LATEST:
        return Finding("cpu_microcode", "ok", "microcode_ok", params)
    if revision >= RAPTOR_FIXED:
        return Finding("cpu_microcode", "info", "microcode_newer", params)
    # Crashes already: the processor may have degraded, a BIOS update only stops it getting worse
    since = _days_ago(facts, EVENT_DAYS)
    unstable = any(e["id"] in WHEA_UNSTABLE + WHEA_FATAL and e["time"] >= since for e in facts.get("whea") or []) or \
        any(e["id"] == 1001 and "systemerrorreporting" in e["provider"].lower() and e["time"] >= since
            for e in facts.get("events") or [])
    return Finding("cpu_microcode", "problem" if unstable else "warning", "microcode_old", params)


def check_x3d_cores(facts):
    cpu_info = facts.get("processor")
    if not cpu_info or not X3D_DUAL.search(cpu_info["name"]):
        return None
    support, bar = facts.get("x3d"), facts.get("game_bar")
    if support is None or bar is None:
        return unknown("x3d_cores")
    items = []
    if not support["driver"]:
        items.append(("item_x3d_driver", {}))
    if not bar["installed"]:
        items.append(("item_game_bar_missing", {}))
    elif not bar["game_mode"]:
        items.append(("item_game_mode_off", {}))
    params = {"name": cpu_info["name"]}
    if items:
        return Finding("x3d_cores", "warning", "x3d_missing", params, items, ["services"])
    return Finding("x3d_cores", "ok", "x3d_ok", params)


def check_power_plan(facts):
    state = facts.get("power")
    if not state:
        return unknown("power_plan")
    plugged = state["plugged"] is not False or not state["battery"]  # a desktop is always plugged in
    params = {"name": state["name"] or "?"}
    # No sleep at all, and a setting known to take it away: Modern Standby turned off on a PC without S3, or the
    # policy that forbids the standby states
    sleep = facts.get("sleep") or {}
    items = [("item_sleep_" + cause, {}) for cause in sleep.get("causes") or []] \
        if sleep.get("available") is False else []
    if plugged and state["scheme"] == POWER_SAVER:
        return Finding("power_plan", "warning", "power_saver", params, items, ["power"])
    if plugged and state["overlay"] == OVERLAY_EFFICIENCY:
        return Finding("power_plan", "warning", "power_efficiency", params, items, ["power_mode"])
    if state.get("idle_disable") == 1:
        return Finding("power_plan", "warning", "idle_off", params, items, ["power"])
    if plugged:
        caps = [state.get(key) for key in ("max_cpu", "max_cpu1") if state.get(key) is not None]
        if caps and min(caps) < 100:
            return Finding("power_plan", "warning", "power_capped", dict(params, percent=min(caps)), items, ["power"])
        if state.get("boost") == 0:
            return Finding("power_plan", "warning", "boost_off", params, items, ["power"])
        mhz = [state.get(key) for key in ("max_mhz", "max_mhz1") if state.get(key)]
        if mhz:
            return Finding("power_plan", "warning", "freq_capped", dict(params, mhz=min(mhz)), items, ["power"])
    if items:
        return Finding("power_plan", "info", "sleep_off", params, items, ["power"])
    if state["saver"]:
        return Finding("power_plan", "info", "battery_saver", params, actions=["power_mode"])
    return Finding("power_plan", "ok", "power_ok", params, actions=["power"])


def pci_vendor(device_id):
    """The PCI vendor ID of a device ("10DE"), or None for a remote, virtual or USB display."""
    found = re.search(r"VEN_([0-9A-F]{4})", (device_id or "").upper())
    return found.group(1) if found and (device_id or "").upper().startswith("PCI\\") else None


def is_discrete(vendor, name):
    """Whether a graphics adapter is a card of its own rather than the processor's graphics."""
    return vendor == NVIDIA or vendor in (AMD, INTEL) and bool(DISCRETE_NAMES.search(name or ""))


def _vendor_of(facts, name):
    card = next((v for v in facts.get("video") or [] if v.get("name") == name), None)
    return pci_vendor(card.get("pnp")) if card else None


def _driver_date(card):
    try:
        return datetime.datetime.fromisoformat(card.get("date") or "").date()
    except ValueError:
        return None


def nvidia_version(driver):
    """NVIDIA's own driver number from the Windows driver version: 32.0.15.8194 -> 581.94."""
    parts = (driver or "").split(".")
    if len(parts) < 4 or not parts[2].isdigit() or not parts[3].isdigit():
        return None
    digits = (parts[2] + parts[3].zfill(4))[-5:]
    return float(digits[:3] + "." + digits[3:])


def check_graphics_driver(facts):
    video = facts.get("video")
    if video is None:
        return unknown("graphics_driver")
    cards = [v for v in video if pci_vendor(v.get("pnp"))]
    # A graphics card turned off in Device Manager: games then run on the processor's graphics
    disabled = [d for d in facts.get("devices") or [] if d.get("code") == 22 and (d.get("cls") or "") == "Display"
                and pci_vendor(d.get("pnp")) and is_discrete(pci_vendor(d.get("pnp")), d.get("name"))]
    if not cards and not disabled:
        return None  # no graphics card on the PCI bus: a virtual machine or a remote session
    items = []
    for card in cards:
        date = _driver_date(card)
        params = {"name": card.get("name") or "?", "version": card.get("version") or "?"}
        items.append(("item_adapter", dict(params, date=date)) if date else ("item_adapter_nodate", params))
    if disabled:
        return Finding("graphics_driver", "warning", "card_disabled", {"name": disabled[0].get("name") or "?"}, items,
                       ["devices"])
    # Without its own driver a card runs on the Microsoft Basic Display Adapter (display.inf). Virtual machines and
    # server management chips use it on purpose, so only the three makers of graphics for PCs count
    basic = [c for c in cards if (c.get("inf") or "").lower() == "display.inf" and pci_vendor(c.get("pnp")) in
             (NVIDIA, AMD, INTEL)]
    if basic:
        return Finding("graphics_driver", "problem", "basic_driver", {"name": basic[0].get("name") or "?"}, items,
                       ["devices", "update"])
    discrete = [c for c in cards if is_discrete(pci_vendor(c.get("pnp")), c.get("name"))]
    main = (discrete or cards)[0]
    date = _driver_date(main)
    params = {"name": main.get("name") or "?", "date": date}
    windows_info = facts.get("windows") or {}
    for card in cards:
        version = nvidia_version(card.get("version")) if pci_vendor(card.get("pnp")) == NVIDIA else None
        if version and version < NVIDIA_FIXED and windows_info.get("build") in (26100, 26200) and \
                windows_info.get("update", 0) >= NVIDIA_SLOW_FROM:
            return Finding("graphics_driver", "warning", "nvidia_slow", {"name": card.get("name") or "?",
                                                                         "version": f"{version:.2f}"}, items, ["update"])
    # Only a graphics card's driver is judged by its age: the processor's graphics get theirs from the PC maker
    if discrete and date and (facts["now"].date() - date).days > OLD_DRIVER_DAYS:
        return Finding("graphics_driver", "info", "driver_old", params, items, ["update"])
    return Finding("graphics_driver", "ok", "driver_ok" if date else "driver_ok_nodate", params, items)


def check_display_output(facts):
    screens, video = facts.get("displays"), facts.get("video")
    if screens is None or video is None:
        return unknown("display_output")
    if not _desktop(facts):
        return None  # a laptop sends the picture through the processor's graphics by design
    cards = [v for v in video if pci_vendor(v.get("pnp")) and not v.get("code")]
    discrete = [c for c in cards if is_discrete(pci_vendor(c.get("pnp")), c.get("name"))]
    attached = [s for s in screens if s.get("vendor")]
    if not discrete or not attached:
        return None  # nothing to compare: one kind of graphics only
    elsewhere = [s for s in attached if not is_discrete(s["vendor"], s.get("adapter"))]
    if not elsewhere:
        return Finding("display_output", "ok", "output_ok", {"name": discrete[0].get("name") or "?"})
    primary = [s for s in elsewhere if s.get("primary")]
    severity = "warning" if primary or len(elsewhere) == len(attached) else "info"
    screen = (primary or elsewhere)[0]
    return Finding("display_output", severity, "output_igpu", {"number": screen["number"],
                                                               "adapter": screen.get("adapter") or "?",
                                                               "card": discrete[0].get("name") or "?"})


def check_gpu_link(facts):
    links, video = facts.get("links"), facts.get("video")
    if not links or video is None or not _desktop(facts):
        return None  # laptops and external cards run on fewer lanes by design
    cards = [v for v in video if is_discrete(pci_vendor(v.get("pnp")), v.get("name"))
             and links.get(v.get("name"))]
    if not cards:
        return None
    for card in cards:
        width, maximum = links[card["name"]]
        if width * 4 <= maximum:  # x4 of x16: the card waits for data
            return Finding("gpu_link", "warning", "link_narrow", {"name": card["name"], "width": width,
                                                                  "max": maximum})
    width, maximum = links[cards[0]["name"]]
    return Finding("gpu_link", "ok", "link_ok", {"name": cards[0]["name"], "width": width, "max": maximum})


def check_gpu_preference(facts):
    programs, video = facts.get("gpu_preferences"), facts.get("video") or []
    has_card = any(is_discrete(pci_vendor(v.get("pnp")), v.get("name")) for v in video)
    if not programs or not has_card:
        return None  # nothing set to power saving, or nothing to choose between
    items = [("item_name", {"name": os.path.basename(path) or path}) for path in programs[:10]]
    return Finding("gpu_preference", "info", "gpu_power_saving", {"n": len(programs)}, items, ["graphics_settings"])


def check_refresh_rate(facts):
    screens = facts.get("displays")
    if screens is None:
        return unknown("refresh_rate")
    if not screens:
        return None  # no display attached to the desktop (a remote session): nothing to say
    items = [("item_display", {"number": s["number"], "width": s["width"], "height": s["height"], "hz": s["hz"],
                               "max_hz": max(s["max_hz"], s["hz"])}) for s in screens]
    slow = [s for s in screens if s["max_hz"] >= s["hz"] + 10 and s["hz"] > 1]
    if slow:
        s = slow[0]
        # On battery laptops lower the rate on purpose to save power
        on_battery = (facts.get("power") or {}).get("plugged") is False
        return Finding("refresh_rate", "info" if on_battery else "warning", "hz_low",
                       {"number": s["number"], "hz": s["hz"], "max_hz": s["max_hz"]}, items, ["display"])
    return Finding("refresh_rate", "ok", "hz_ok", {"hz": screens[0]["hz"]}, items, ["display"])


def check_startup_apps(facts):
    names = facts.get("startup")
    if names is None:
        return unknown("startup_apps")
    # What the programs cost at the last starts, as Task Manager's "Startup impact" measures it: "High" is more
    # than a second of processor time or more than 3 MB read from the drive
    heavy = [p for p in facts.get("startup_impact") or []
             if p["cpu"] >= STARTUP_HIGH_MS or p["disk"] >= STARTUP_HIGH_DISK]
    items = [("item_startup_heavy", {"name": p["name"], "seconds": round(p["cpu"] / 1000, 1), "size": Size(p["disk"])})
             for p in heavy[:5]]
    items += [("item_name", {"name": name}) for name in sorted(names, key=str.lower)]
    if len(names) > 10:
        return Finding("startup_apps", "warning", "startup_many", {"n": len(names)}, items, ["startup"])
    if heavy:
        return Finding("startup_apps", "info", "startup_heavy",
                       {"n": len(names), "names": ", ".join(p["name"] for p in heavy[:3])}, items, ["startup"])
    return Finding("startup_apps", "ok", "startup_ok", {"n": len(names)}, items, ["startup"])


def check_rgb_software(facts):
    running = facts.get("processes")
    if running is None:
        return None
    products = sorted({RGB_PROGRAMS[name] for name in running if name in RGB_PROGRAMS})
    if len(products) < 2:
        return None  # one lighting program or none: nothing to fight over
    return Finding("rgb_software", "info", "rgb_many", {"names": ", ".join(products)}, actions=["startup"])


def check_game_dvr(facts):
    state = facts.get("game_dvr")
    if state is None:
        return unknown("game_dvr")
    if state["background"]:
        return Finding("game_dvr", "warning", "dvr_on", actions=["captures"])
    return Finding("game_dvr", "ok", "dvr_ok")


def check_boot_options(facts):
    boot = facts.get("boot")
    if boot is None:
        return unknown("boot_options")
    items = []
    # Fewer processors at work than the processor has: "Number of processors" in msconfig, or the BIOS. The
    # processor's own count comes from the firmware; Windows' count of logical processors follows the limit
    threads = facts.get("cpu_hardware_threads") or facts.get("cpu_threads")
    active = boot.get("processors")
    if threads and active and active < threads:
        items.append(("item_numproc", {"n": active, "total": threads}))
    elif not threads:  # the processor's own count is unknown: the boot option itself is the clue
        items += [("item_numproc_option", {"option": option}) for option in boot["options"]
                  if option.partition("=")[0] in BOOT_PROCESSORS]
    items += [("item_maxmem", {"option": option}) for option in boot["options"]
              if option.partition("=")[0] in BOOT_MEMORY]
    flags = boot.get("integrity")
    if flags is not None:
        if flags & CI_TESTSIGN:
            items.append(("item_testsigning", {}))
        if not flags & CI_ENABLED:
            items.append(("item_integrity", {}))
        if flags & CI_DEBUG:
            items.append(("item_debug", {}))
    if boot.get("timer") == HPET_FREQUENCY:
        items.append(("item_hpet", {}))
    if boot["verifier"]:
        items.append(("item_verifier", {}))
    if boot["tdr_off"]:
        items.append(("item_tdr_off", {}))
    if not items:
        return Finding("boot_options", "ok", "boot_ok")
    return Finding("boot_options", "warning", "boot_changed", {"n": len(items)}, items, ["system_config"])


def check_throttling(facts):
    events = facts.get("throttle_events")
    if not events or not _desktop(facts):
        return None  # laptops slow down on battery and when warm by design
    since = _days_ago(facts, THROTTLE_DAYS)
    seconds = 0
    for e in events:
        if e["time"] >= since and len(e["args"]) > 2 and e["args"][2].isdigit():
            seconds += int(e["args"][2])
    if seconds < THROTTLE_SECONDS:
        return None
    return Finding("throttling", "info", "throttled", {"hours": round(seconds / 3600, 1), "days": THROTTLE_DAYS},
                   actions=["events"])


def check_uptime(facts):
    seconds = facts.get("uptime")
    if seconds is None:
        return unknown("uptime")
    since = facts["now"] - datetime.timedelta(seconds=seconds)
    days = seconds / 86400
    items = [("item_fast_startup", {})] if facts.get("fast_startup") else []
    severity = "warning" if days >= 7 else "ok"
    return Finding("uptime", severity, "uptime", {"date": since.date(), "days": int(days)}, items)


def check_disk_space(facts):
    found = facts.get("drives")
    if not found:
        return unknown("disk_space")
    verdicts = {}
    for d in found:
        free, share = d["free"], d["free"] / d["total"] if d["total"] else 1
        # Windows needs room on its own drive for updates and the page file; another drive only gets full
        if d["system"]:
            if free < 5 * GB:
                verdicts[d["drive"]] = "problem"
            elif free < 20 * GB or share < 0.05 and free < 50 * GB:
                verdicts[d["drive"]] = "warning"
        elif free < 2 * GB or share < 0.03:
            verdicts[d["drive"]] = "info"
    worst = min(verdicts.values(), key=SEVERITIES.index) if verdicts else "ok"
    items = [("item_drive", {"drive": d["drive"], "free": Size(d["free"]), "total": Size(d["total"]),
                             "percent": _percent(d["free"], d["total"])}) for d in found]
    if worst == "ok":
        return Finding("disk_space", "ok", "space_ok", {}, items, ["storage"])
    d = min((d for d in found if d["drive"] in verdicts), key=lambda d: (SEVERITIES.index(verdicts[d["drive"]]),
                                                                        d["free"]))
    return Finding("disk_space", worst, "space_low", {"drive": d["drive"], "free": Size(d["free"]),
                                                      "total": Size(d["total"])}, items, ["storage"])


def _health(disk):
    """The health a drive reports, in the window's language when it is one of the usual three."""
    health = disk.get("health") or "?"
    return Text("health_" + health.lower()) if health.lower() in ("healthy", "warning", "unhealthy") else health


def check_disk_health(facts):
    disks = facts.get("disks")
    if not disks:
        return unknown("disk_health")
    # Wear and uncorrected read errors: only administrators can read them, and some drives leave them empty. What
    # an NVMe drive or a hard disk reports itself comes first: Windows' counters can show no wear at all
    counters = {c.get("id"): c for c in facts.get("wear") or []}
    own = facts.get("drive_health") or {}
    items = []
    for d in disks:
        params = {"name": d.get("name") or "?", "media": d.get("media") or "?", "bus": d.get("bus") or "?",
                  "health": _health(d)}
        report = own.get(d.get("id"))
        wear = counters.get(d.get("id"), {}).get("wear")
        if report and report["kind"] == "nvme":
            items.append(("item_disk_nvme", dict(params, wear=report["used"], hours=report["hours"],
                                                 written=Size(report["written"]), unsafe=report["unsafe"])))
        elif report and report["kind"] == "ata":
            items.append(("item_disk_hdd", dict(params, hours=report["hours"] or 0)))
        elif isinstance(wear, int):
            items.append(("item_disk_wear", dict(params, wear=wear)))
        else:
            items.append(("item_disk", params))
    # "Unknown" comes from USB bridges, RAID and virtual disks: no data rather than a fault
    bad = [d for d in disks if (d.get("health") or "").lower() in ("warning", "unhealthy")]
    if bad:
        severity = "problem" if any(d["health"].lower() == "unhealthy" for d in bad) else "warning"
        return Finding("disk_health", severity, "health_bad", {"name": bad[0].get("name") or "?",
                                                               "health": _health(bad[0])}, items)
    found = [drive_verdict(d, own.get(d.get("id")), counters.get(d.get("id"), {})) for d in disks]
    found = [f for f in found if f]
    if found:
        severity, line, params = min(found, key=lambda f: SEVERITIES.index(f[0]))
        return Finding("disk_health", severity, line, params, items)
    return Finding("disk_health", "ok", "health_ok", {}, items)


def drive_verdict(disk, report, counter):
    """(severity, line, params) of what one drive reports about its health, or None when it is fine. The rules
    are CrystalDiskInfo's: an NVMe drive's critical warning, its spare blocks at or below the threshold, its rated
    endurance used up; a hard disk's reallocated, pending or uncorrectable sectors."""
    params = {"name": disk.get("name") or "?"}
    if report and report["kind"] == "nvme":
        critical = report["critical"]
        if critical & ~0x02:  # spare low, reliability degraded, read-only, the backup of volatile memory failed
            return "problem", "nvme_critical", params
        if report["spare_threshold"] and report["spare"] < report["spare_threshold"]:
            return "problem", "nvme_spare", dict(params, spare=report["spare"])
        if report["used"] >= NVME_WORN:
            return "problem" if report["used"] >= NVME_WORN_OUT else "warning", "ssd_worn", \
                dict(params, wear=report["used"])
        if report["spare_threshold"] and report["spare"] == report["spare_threshold"]:
            return "warning", "nvme_spare", dict(params, spare=report["spare"])
        if report["media_errors"]:
            return "warning", "nvme_media_errors", dict(params, n=report["media_errors"])
        if critical & 0x02:
            return "warning", "nvme_hot", dict(params, temperature=report["temperature"] or "?")
        return None
    if report and report["kind"] == "ata":
        sectors = {key: report[key] or 0 for key in ("reallocated", "pending", "uncorrectable")}
        if any(sectors.values()):
            return "warning", "hdd_sectors", dict(params, **sectors)
        return None
    wear, errors = counter.get("wear"), counter.get("read_errors")
    if isinstance(wear, int) and wear >= NVME_WORN:
        return "problem" if wear >= NVME_WORN_OUT else "warning", "ssd_worn", dict(params, wear=wear)
    if isinstance(errors, int) and errors > 0:
        return "warning", "read_errors", dict(params, n=errors)
    return None


def check_system_drive(facts):
    disks, number = facts.get("disks"), facts.get("system_disk")
    if not disks or number is None:
        return unknown("system_drive")
    system = [d for d in disks if d.get("id") == str(number)]
    if not system:
        return unknown("system_drive")
    disk = system[0]
    params = {"name": disk.get("name") or "?", "bus": disk.get("bus") or "?"}
    if (disk.get("bus") or "").upper() in REMOVABLE_BUSES:  # eMMC, a memory card or a USB drive
        return Finding("system_drive", "warning", "system_slow_bus", params)
    if (disk.get("media") or "").upper() not in ("HDD", "SSD"):
        return None  # a virtual machine or a drive that does not say what it is
    if disk["media"].upper() == "HDD":
        return Finding("system_drive", "warning", "system_hdd", params)
    if facts.get("trim_off"):
        return Finding("system_drive", "warning", "ssd_trim_off", params)
    return Finding("system_drive", "ok", "system_ssd", params)


def check_disk_errors(facts):
    events = facts.get("disk_events")
    if events is None:
        return unknown("disk_errors")
    since, kinds = _days_ago(facts, EVENT_DAYS), {}
    buses = {d.get("id"): (d.get("bus") or "").upper() for d in facts.get("disks") or []}
    internal = False
    for e in events:
        provider = e["provider"].lower().replace("microsoft-windows-", "")
        kind = DISK_EVENTS.get((provider, e["id"]))
        if kind is None and e["id"] == 129 and provider in STORAGE_RESET_PROVIDERS:
            kind = "reset"
        if not kind or e["time"] < since or (e["level"] or 4) > 3:
            continue
        # "\Device\Harddisk2\DR2": errors of a memory stick or card pulled out are normal, and so are those of a disk
        # that is not on the PC any more: its number is not among the disks found now (when they could be listed)
        disk = re.search(r"Harddisk(\d+)", e["args"][0] if e["args"] else "")
        number = disk.group(1) if disk else None
        gone = bool(buses) and number is not None and number not in buses
        removable = provider == "disk" and number is not None and (gone or buses.get(number) in REMOVABLE_BUSES)
        internal = internal or not removable
        count, last, serious = kinds.get(kind, (0, e["time"], False))
        kinds[kind] = (count + 1, max(last, e["time"]), serious or not removable)
    if not kinds:
        return Finding("disk_errors", "ok", "disk_errors_ok", {"days": EVENT_DAYS})
    if not internal:
        severity = "info"
    else:
        severity = "problem" if any(k in DISK_SERIOUS and on_internal for k, (_, _, on_internal) in kinds.items()) \
            else "warning"
    items = [("item_event_kind", {"kind": Text("kind_" + kind), "n": count, "date": last.date()})
             for kind, (count, last, _) in sorted(kinds.items(), key=lambda item: -item[1][0])]
    if not internal:
        items.append(("item_removable", {}))
    return Finding("disk_errors", severity, "disk_errors", {"n": sum(c for c, _, _ in kinds.values()),
                                                            "days": EVENT_DAYS}, items, ["events"])


def check_temp_files(facts):
    temp = facts.get("temp")
    if not temp:
        return unknown("temp_files")
    size, files = temp["size"], temp.get("files")
    items = []
    # Who litters: the biggest entries and the families of loose files with the same name
    for entry in temp.get("top") or []:
        if entry["size"] >= TEMP_TOP_MIN or (entry["size"] >= 100 * MB and entry["size"] >= size / 10):
            if entry["files"] == 1 and not entry["name"].endswith("\\"):
                items.append(("item_temp_file", {"name": entry["name"], "size": Size(entry["size"])}))
            else:
                items.append(("item_temp_top", {"name": entry["name"], "size": Size(entry["size"]), "files": entry["files"]}))
    for family in temp.get("families") or []:
        if family["n"] >= TEMP_FAMILY_MIN:
            items.append(("item_temp_family", {"pattern": family["pattern"], "n": family["n"], "size": Size(family["size"])}))
    cbs, servicing_fault = facts.get("cbs") or {}, False
    largest = cbs.get("largest")
    if largest and largest["size"] >= CBS_LOG_LIMIT:
        items.append(("item_cbs_large", {"name": largest["name"], "size": Size(largest["size"])}))
        servicing_fault = True
    if (cbs.get("cabs") or 0) >= 10:
        items.append(("item_cbs_cabs", {"n": cbs["cabs"]}))
        servicing_fault = True
    many = files is not None and files >= TEMP_MANY_FILES
    params = {"size": Size(size), "files": files or 0}
    if temp["partial"]:
        line = "temp_many_partial" if many else "temp_size_partial"
    else:
        line = "temp_many" if many else "temp_size"
    severity = "warning" if size >= 5 * GB or many or servicing_fault else "ok"
    return Finding("temp_files", severity, line, params, items, ["temp", "storage"] if severity != "ok" else [])


def check_crashes(facts):
    events = facts.get("events")
    if events is None:
        return unknown("crashes")
    since = _days_ago(facts, EVENT_DAYS)
    recent = [e for e in events if e["time"] >= since]
    # A blue screen is recorded as BugCheck 1001 after the restart and as Kernel-Power 41 with its stop code
    reports = [e for e in recent if e["id"] == 1001 and "systemerrorreporting" in e["provider"].lower()]
    powers = [e for e in recent if e["id"] == 41 and "kernel-power" in e["provider"].lower()]
    stops = [e for e in powers if e["args"] and e["args"][0] not in ("0", "")]
    resets = [e for e in powers if not e["args"] or e["args"][0] in ("0", "")]
    if not powers:  # some PCs log only "the previous shutdown was unexpected"
        resets = [e for e in recent if e["id"] == 6008 and e["provider"].lower() == "eventlog"]
    blue = reports or stops
    items = []
    for e in sorted(blue, key=lambda e: e["time"], reverse=True)[:6]:
        code = e["args"][0].split()[0] if e["args"] else "?"
        if e["id"] == 41 and code.isdigit():
            code = f"0x{int(code):08X}"
        cause = stop_cause(code)
        items.append(("item_bsod_cause", {"date": e["time"].date(), "code": code, "cause": Text("stop_" + cause)})
                     if cause else ("item_bsod", {"date": e["time"].date(), "code": code}))
    for e in sorted(resets, key=lambda e: e["time"], reverse=True)[:6]:
        # Kernel-Power 41 keeps when the power button was pressed, and the power state Windows was moving to at the
        # time (SYSTEM_POWER_STATE): 2-4 sleep, 5 hibernation (and Fast startup), 6 shutdown
        args = e["args"] if e["id"] == 41 else []
        state = int(args[5]) if len(args) > 5 and args[5].isdigit() else 0
        if len(args) > 6 and args[6] not in ("0", ""):
            key = "item_reset_button"
        elif state in (5, 6):
            key = "item_reset_shutdown"
        elif state in (2, 3, 4):
            key = "item_reset_sleep"
        else:
            key = "item_reset"
        items.append((key, {"date": e["time"].date()}))
    # The dump files are a second witness: they stay when the log was cleared or the events were never written
    kernel = facts.get("kernel_dumps") or {}
    minidumps = [moment for moment in kernel.get("minidumps") or [] if moment >= since]
    last_crash = kernel.get("last_crash")
    if not blue and minidumps:
        items = [("item_minidump", {"date": moment.date()}) for moment in minidumps[:6]] + items
        blue = minidumps
    elif not blue and last_crash and last_crash >= since:
        items.insert(0, ("item_last_crash", {"date": last_crash.date()}))
        blue = [last_crash]
    actions = ["reliability"]
    if kernel.get("enabled") == 0:
        items.append(("item_dumps_disabled", {}))
        actions.append("system_properties")
    memory = kernel.get("memory_dmp")
    if memory and memory["size"] >= GB:
        items.append(("item_memory_dmp", {"date": memory["time"].date(), "size": Size(memory["size"])}))
    if blue:
        return Finding("crashes", "problem", "bsod", {"n": len(blue), "days": EVENT_DAYS}, items, actions)
    if resets:
        return Finding("crashes", "warning", "resets", {"n": len(resets), "days": EVENT_DAYS}, items, actions)
    return Finding("crashes", "ok", "crashes_ok", {"days": EVENT_DAYS}, items, actions[1:])


# The usual cause behind the commonest stop codes of a blue screen (Microsoft's bug check reference)
STOP_CAUSES = {
    "driver": (0x0A, 0x1E, 0x3B, 0x7E, 0x8E, 0xC2, 0xC5, 0xD1, 0x19, 0xBE, 0xFC, 0x13A, 0x139, 0x133, 0xCE, 0xD5),
    "memory": (0x1A, 0x50, 0x12B, 0x4E),
    "graphics": (0x116, 0x117, 0x119, 0x10E, 0x141),
    "hardware": (0x124, 0x101, 0x9C),
    "disk": (0x7A, 0x77, 0x154, 0x24, 0x7B),
    "system": (0xEF, 0xF4, 0xC000021A),
    "sleep": (0x9F, 0xA0),
    "usb": (0x144, 0xFE),
}


def stop_cause(code):
    """The kind of fault a stop code usually means ("driver", "memory"…), or None for one not in STOP_CAUSES."""
    try:
        number = int(str(code), 16)
    except ValueError:
        return None
    return next((cause for cause, codes in STOP_CAUSES.items() if number in codes), None)


def _module_vendor(module):
    """The maker of a graphics driver module by its name: nvwgf2umx.dll -> NVIDIA."""
    module = (module or "").lower()
    if module.startswith("nv"):
        return NVIDIA
    if module.startswith(("amd", "ati")):
        return AMD
    if module.startswith("ig"):
        return INTEL
    return None


def shader_cache_folder(vendor):
    """Where the graphics driver keeps its compiled shaders; a damaged cache makes games stutter or crash."""
    return {NVIDIA: r"%LocalAppData%\NVIDIA\DXCache", AMD: r"%LocalAppData%\AMD\DxCache",
            INTEL: r"%LocalAppData%\Intel\ShaderCache"}.get(vendor)


def _module_kind(module):
    """("overlay", product) or ("gpu", None) for a module a crash happened in, or None."""
    module = (module or "").lower()
    if module in OVERLAY_MODULES:
        return "overlay", OVERLAY_MODULES[module]
    for prefix, product in OVERLAY_PREFIXES.items():
        if module.startswith(prefix):
            return "overlay", product
    if module.startswith(GPU_MODULES):
        return "gpu", None
    return None


def check_app_crashes(facts):
    events = facts.get("app_events")
    if events is None:
        return unknown("app_crashes")
    since, apps, modules, codes = _days_ago(facts, APP_EVENT_DAYS), {}, {}, {}
    for e in events:
        if e["time"] < since or not e["args"] or e["id"] not in (1000, 1002):
            continue
        name = os.path.basename(e["args"][0]) or e["args"][0]
        crashes, hangs = apps.get(name, (0, 0))
        apps[name] = (crashes + (e["id"] == 1000), hangs + (e["id"] == 1002))
        if e["id"] == 1000 and len(e["args"]) > 6:
            # Application Error: [3] the module the crash happened in, [6] the exception code
            module, code = e["args"][3], e["args"][6].lower().replace("0x", "")
            modules.setdefault(name, {}).setdefault(module, 0)
            modules[name][module] += 1
            codes.setdefault((code, module.lower()), set()).add(name)
    if not apps:
        return Finding("app_crashes", "ok", "app_crashes_ok", {"days": APP_EVENT_DAYS})
    ranked = sorted(apps.items(), key=lambda item: -sum(item[1]))
    items = []
    for name, (c, h) in ranked[:8]:
        module = max(modules.get(name, {"": 0}).items(), key=lambda item: item[1])[0]
        if module:
            items.append(("item_app_crash_module", {"name": name, "crashes": c, "hangs": h, "module": module}))
        else:
            items.append(("item_app_crash", {"name": name, "crashes": c, "hangs": h}))
    # Dumps Windows Error Reporting saved locally for these crashes: a developer can read them
    dumps = {}
    for dump in (facts.get("local_dumps") or {}).get("dumps") or []:
        if dump["time"] >= since:
            entry = dumps.setdefault(dump["name"].lower(), {"n": 0, "size": 0, "folder": dump["folder"]})
            entry["n"], entry["size"] = entry["n"] + 1, entry["size"] + dump["size"]
    for name, _ in ranked[:8]:
        saved = dumps.get(name.lower()) or dumps.get(name.lower().removesuffix(".exe"))
        if saved:
            items.append(("item_dumps_saved", {"name": name, "n": saved["n"], "folder": saved["folder"],
                                               "size": Size(saved["size"])}))
    # Hints from the modules and the codes: an overlay, the graphics driver, the drive, unstable hardware
    hinted = set()
    for name, _ in ranked[:8]:
        for module in modules.get(name, {}):
            kind = _module_kind(module)
            if kind and (kind[0], module.lower()) not in hinted:
                hinted.add((kind[0], module.lower()))
                if kind[0] == "overlay":
                    items.append(("item_hint_overlay", {"module": module, "product": kind[1]}))
                else:
                    items.append(("item_hint_gpu", {"module": module}))
                    folder = shader_cache_folder(_module_vendor(module))
                    if folder and ("item_shader_cache", {"folder": folder}) not in items:
                        items.append(("item_shader_cache", {"folder": folder}))
    if any(code == CRASH_IN_PAGE for code, _ in codes):
        items.append(("item_hint_disk", {"code": "0x" + CRASH_IN_PAGE.upper()}))
    illegal = any(code == CRASH_ILLEGAL for code, _ in codes)
    widespread = any(len(names) >= UNSTABLE_PROGRAMS for (code, module), names in codes.items()
                     if code == CRASH_ACCESS and module in CRASH_SYSTEM_MODULES)
    if illegal or widespread:
        items.append(("item_hint_unstable", {}))
    severity = "warning" if sum(ranked[0][1]) >= 3 else "info"
    return Finding("app_crashes", severity, "app_crashes", {"n": sum(sum(v) for v in apps.values()),
                                                            "days": APP_EVENT_DAYS, "name": ranked[0][0]},
                   items, ["reliability"])


def check_gpu_resets(facts):
    events, nvidia_events = facts.get("events"), facts.get("nvidia_events")
    if events is None:
        return unknown("gpu_resets")
    since = _days_ago(facts, EVENT_DAYS)

    def minute(moment):
        return moment.replace(second=0, microsecond=0)

    # Windows restarting a driver that stopped responding (TDR), the NVIDIA driver restarting itself, and Windows'
    # own reports of a graphics engine that stopped responding (live kernel events 117 and 141). One incident
    # leaves several of these within a minute, so incidents are counted by the minute
    resets = {minute(e["time"]) for e in events if e["id"] == 4101 and e["provider"].lower() == "display"
              and e["time"] >= since}
    nvidia = [e for e in nvidia_events or [] if e["time"] >= since and (e["level"] or 4) <= 2]
    restarts = {minute(e["time"]) for e in nvidia if e["id"] == NVIDIA_RESET}
    # Graphics exceptions without a restart are often the program's own fault
    exceptions = {minute(e["time"]) for e in nvidia if e["id"] in NVIDIA_EXCEPTIONS} - restarts
    hangs = {minute(e["time"]) for e in facts.get("live_events") or []
             if e["time"] >= since and len(e["args"]) > 5 and e["args"][5].upper() in GPU_HANGS}
    items = [("item_name", {"name": adapter}) for adapter in facts.get("graphics", [])]
    if facts.get("wer_off"):
        items.append(("item_wer_off", {}))
    incidents = resets | restarts | hangs
    if not incidents and not exceptions:
        return Finding("gpu_resets", "ok", "tdr_ok", {"days": EVENT_DAYS}, items)
    for kind, times in (("kind_tdr", resets), ("kind_nvidia", restarts), ("kind_gpu_hang", hangs),
                        ("kind_nvidia_exception", exceptions)):
        if times:
            items.append(("item_event_kind", {"kind": Text(kind), "n": len(times), "date": max(times).date()}))
    if not incidents:
        return Finding("gpu_resets", "info", "gpu_exceptions", {"n": len(exceptions), "days": EVENT_DAYS}, items,
                       ["devices"])
    # The shader cache advice for the graphics card, or for the processor's graphics when there is no card
    cards = sorted(facts.get("video") or [], key=lambda c: not is_discrete(pci_vendor(c.get("pnp")), c.get("name")))
    for card in cards:
        folder = shader_cache_folder(pci_vendor(card.get("pnp")))
        if folder:
            items.append(("item_shader_cache", {"folder": folder}))
            break
    severity = "problem" if len(resets) >= 3 or len(incidents) >= 10 else "warning"
    return Finding("gpu_resets", severity, "tdr", {"n": len(incidents), "days": EVENT_DAYS}, items, ["devices"])


def check_whea(facts):
    events = facts.get("whea")
    if events is None:
        return unknown("whea")
    since = _days_ago(facts, EVENT_DAYS)
    recent = [e for e in events if e["time"] >= since]
    fatal = [e for e in recent if e["id"] in WHEA_FATAL or (e["level"] or 4) <= 2]
    unstable = [e for e in recent if e["id"] in WHEA_UNSTABLE and e not in fatal]
    pcie = [e for e in recent if e["id"] == WHEA_PCIE and e not in fatal]
    other = [e for e in recent if e not in fatal and e not in unstable and e not in pcie]
    items = [("item_event_kind", {"kind": Text(kind), "n": len(found), "date": max(e["time"] for e in found).date()})
             for kind, found in (("kind_whea_fatal", fatal), ("kind_whea_unstable", unstable),
                                 ("kind_whea_pcie", pcie), ("kind_whea_other", other)) if found]
    if fatal:
        return Finding("whea", "problem", "whea_fatal", {"n": len(fatal), "days": EVENT_DAYS}, items, ["events"])
    if unstable:  # corrected errors in the processor or memory: overclocking, XMP/EXPO or a failing part
        return Finding("whea", "warning", "whea_unstable", {"n": len(unstable), "days": EVENT_DAYS}, items, ["events"])
    corrected = pcie + other
    if corrected:
        per_day = {}
        for e in pcie:
            per_day[e["time"].date()] = per_day.get(e["time"].date(), 0) + 1
        storm = max(per_day.values(), default=0) > WHEA_PCIE_STORM
        severity = "warning" if storm or len(other) >= 10 else "info"
        return Finding("whea", severity, "whea_corrected", {"n": len(corrected), "days": EVENT_DAYS}, items,
                       ["events"])
    return Finding("whea", "ok", "whea_ok", {"n": 0, "days": EVENT_DAYS})


def check_memory_test(facts):
    tests = facts.get("memory_tests")
    if not tests:
        return None  # Windows Memory Diagnostic has not run on this PC, or its result cannot be read
    last = max(tests, key=lambda e: e["time"])
    if last["id"] in (1102, 1202):
        return Finding("memory_test", "problem", "memtest_errors", {"date": last["time"].date()},
                       actions=["events"])
    return Finding("memory_test", "ok", "memtest_ok", {"date": last["time"].date()})


def check_devices(facts):
    devices = facts.get("devices")
    if devices is None:
        return unknown("devices")
    broken = [d for d in devices if d.get("code") not in DEVICE_IGNORED and d.get("code")]
    if not broken:
        return Finding("devices", "ok", "devices_ok")
    items = [("item_device", {"name": d.get("name") or "?", "code": d["code"],
                              "problem": Text(f"code_{d['code']}" if d["code"] in DEVICE_CODES else "code_other")})
             for d in broken[:10]]
    conflict = any(d["code"] == 12 for d in broken)
    return Finding("devices", "warning", "devices_conflict" if conflict else "devices", {"n": len(broken)}, items,
                   ["devices"])


def check_services(facts):
    events = facts.get("service_events")
    if events is None:
        return unknown("services")
    since, failures = _days_ago(facts, SERVICE_DAYS), {}
    shutdowns = [e["time"] for e in facts.get("shutdowns") or []]
    for e in events:
        if e["time"] < since or not e["args"] or not e["args"][0]:
            continue
        name = e["args"][0]
        if name.lower() in SERVICES_IGNORED or PER_USER_SERVICE.search(name):
            continue
        # A service that stops badly while Windows shuts down does no harm
        if e["id"] in (7031, 7034) and any(abs(e["time"] - moment) <= SHUTDOWN_GRACE for moment in shutdowns):
            continue
        failures[name] = failures.get(name, 0) + 1
    failing = sorted(((n, c) for n, c in failures.items() if c >= SERVICE_FAILURES), key=lambda item: -item[1])
    if not failing:
        return Finding("services", "ok", "services_ok", {"days": SERVICE_DAYS})
    items = [("item_service", {"name": name, "n": count}) for name, count in failing[:8]]
    return Finding("services", "warning", "services_failing", {"n": len(failing), "days": SERVICE_DAYS}, items,
                   ["services", "events"])


def check_core_services(facts):
    found = facts.get("disabled_services")
    if found is None:
        return unknown("core_services")
    small = (facts.get("memory") or {}).get("total", 0) <= SMALL_MEMORY
    core = {name for name, _ in CORE_SERVICES}
    # SysMain off matters only where it also compresses memory
    found = [f for f in found if f[2] != "compression" or small]
    if not found:
        return Finding("core_services", "ok", "core_ok")
    items = [("item_service_off", {"name": display, "effect": Text("effect_" + effect)})
             for _, display, effect in found]
    severity = "warning" if any(name in core for name, _, _ in found) else "info"
    return Finding("core_services", severity, "core_off", {"n": len(found)}, items, ["services"])


def check_system_files(facts):
    state = facts.get("image")
    if state is None:
        return unknown("system_files", "unknown_admin" if facts.get("admin") is False else "unknown_read")
    if state.lower() == "nonrepairable":
        return Finding("system_files", "problem", "image_broken", actions=["recovery"])
    if state.lower() == "repairable":
        return Finding("system_files", "warning", "image_repairable")
    return Finding("system_files", "ok", "image_ok")


def check_vc_runtime(facts):
    found = facts.get("vc_runtime")
    if found is None:
        return unknown("vc_runtime")
    items, worst = [], "ok"
    for kind in ("x64", "x86"):
        version = found.get(kind)
        if version is None:
            items.append(("item_runtime_missing", {"kind": kind}))
            worst = min(worst, "info", key=SEVERITIES.index)
        else:
            text = ".".join(str(part) for part in version)
            items.append(("item_runtime", {"kind": kind, "version": text}))
            if version[:2] < VC_RUNTIME_MIN:
                worst = "warning"
    line = {"ok": "runtime_ok", "info": "runtime_missing", "warning": "runtime_old"}[worst]
    return Finding("vc_runtime", worst, line, {"min": ".".join(str(p) for p in VC_RUNTIME_MIN)}, items)


def check_media_pack(facts):
    info = facts.get("windows")
    if not info or not info["edition"].endswith("N"):
        return None  # only the N editions of Windows come without Windows Media components
    if info.get("media"):
        return Finding("media_pack", "ok", "media_ok")
    return Finding("media_pack", "warning", "media_missing", actions=["optional_features"])


def check_battery(facts):
    if not (facts.get("power") or {}).get("battery"):
        return None  # a desktop: no battery to check
    battery = facts.get("battery")
    if not battery:
        return unknown("battery")
    health = min(100, _percent(battery["full"], battery["design"]))
    severity = "problem" if health < 40 else "warning" if health < 60 else "ok"
    cycles = facts.get("battery_cycles")
    return Finding("battery", severity, "battery", {"percent": health},
                   [("item_battery_cycles", {"n": cycles})] if cycles else [])


# SecurityCenter2 productState: bits 12-15 say whether protection is on, bits 4-7 whether definitions are current
def antivirus_on(state):
    return (state >> 12) & 0xF == 1


def antivirus_outdated(state):
    return (state >> 4) & 0xF != 0


def check_antivirus(facts):
    if (facts.get("windows") or {}).get("server"):
        return None  # Windows Server has no Security Center
    products = facts.get("antivirus")
    if products is None:
        return unknown("antivirus")
    items = []
    for p in products:
        state = p.get("state") or 0
        key = "av_outdated" if antivirus_on(state) and antivirus_outdated(state) else \
            "av_on" if antivirus_on(state) else "av_off"
        items.append(("item_av", {"name": p.get("name") or "?", "state": Text(key)}))
    active = [p for p in products if antivirus_on(p.get("state") or 0)]
    if not active:
        return Finding("antivirus", "problem", "av_none", {}, items, ["security"])
    names = ", ".join(p.get("name") or "?" for p in active)
    if len(active) > 1:
        return Finding("antivirus", "warning", "av_many", {"names": names}, items, ["security"])
    if antivirus_outdated(active[0].get("state") or 0):
        return Finding("antivirus", "warning", "av_old", {"name": names}, items, ["security"])
    return Finding("antivirus", "ok", "av_ok", {"name": names}, items, ["security"])


def check_security_settings(facts):
    state = facts.get("security")
    if state is None:
        return unknown("security_settings")
    # On a PC an organization manages, its policies are on purpose
    weakened = "info" if _is_managed(facts) else "warning"
    found = []
    if state["uac_off"]:
        found.append(("item_uac_off", {}, "warning"))
    if state["mitigations_off"]:
        found.append(("item_mitigations_off", {}, "warning"))
    if state.get("smartscreen_off"):
        found.append(("item_smartscreen_off", {}, weakened))
    if state.get("zone_off"):
        found.append(("item_zone_off", {}, weakened))
    # Policies that turn Microsoft Defender off: only while it is the antivirus at work. Tamper protection ignores
    # them on a PC no organization manages, and real-time protection then stays on
    defender, policies = facts.get("defender"), state.get("defender_policies") or []
    if policies and defender and defender["mode"].lower().startswith("normal"):
        names = ", ".join(policies)
        if not defender["realtime"]:
            found.append(("item_defender_policy", {"names": names}, weakened))
        elif defender["tamper"]:
            found.append(("item_defender_policy_ignored", {"names": names}, "info"))
        else:
            found.append(("item_defender_policy_pending", {"names": names}, weakened))
    found += [("item_hidden_" + page, {}, "info") for page in state.get("hidden_pages") or []]
    if state.get("notifications_off"):
        found.append(("item_defender_quiet", {}, "info"))
    # The blocklist of vulnerable drivers: memory integrity enforces it anyway, and Windows 10 had it off
    integrity = (facts.get("boot") or {}).get("integrity") or 0
    if state.get("blocklist_off") and not integrity & CI_HVCI and (facts.get("windows") or {}).get("build", 0) >= 22621:
        found.append(("item_blocklist_off", {}, "warning"))
    if not found:
        return Finding("security_settings", "ok", "security_ok")
    severity = min((f[2] for f in found), key=SEVERITIES.index)
    items = [(key, params) for key, params, _ in found]
    by_policy = [f for f in found if f[0] not in ("item_uac_off", "item_mitigations_off")]
    if by_policy and _is_managed(facts):
        items.append(("item_managed", {}))
    actions = ["uac"] if state["uac_off"] else ["security"] if by_policy else []
    return Finding("security_settings", severity, "security_off" if severity == "warning" else "security_changed",
                   {"n": len(found)}, items, actions)


def check_memory_integrity(facts):
    flags = (facts.get("boot") or {}).get("integrity")
    if flags is None or not flags & CI_HVCI:
        return None  # off, or unknown: nothing to point out
    # Without MBEC/GMET Windows emulates what memory integrity needs, and that costs more
    available = (facts.get("vbs") or {}).get("available")
    items = [("item_no_mbec", {})] if available and MBEC not in available else []
    return Finding("memory_integrity", "info", "hvci_on", {}, items, ["core_isolation"])


def check_secure_boot(facts):
    state = facts.get("firmware")
    if state is None or state["tpm"] is None:
        return unknown("secure_boot")
    items = []
    if not state["uefi"]:
        items.append(("item_legacy_boot", {}))
    elif state["secure_boot"] is False:
        items.append(("item_secure_boot_off", {}))
    if state["tpm"] < 2:
        items.append(("item_tpm_missing", {}))
    # With Secure Boot on, the certificates of 2023 must replace those of 2011 for the boot process to get new
    # protections; Windows does it by itself, so only a failure or a long wait is worth saying
    certificates = None
    if state["secure_boot"] and state.get("ca2023") and state["ca2023"].lower() != "updated":
        error = state.get("ca2023_error")
        certificates = ("warning", ("item_ca2023_failed", {"code": f"0x{error & 0xFFFFFFFF:08X}"})) if error else \
            ("info", ("item_ca2023_pending", {}))
    if not items:
        if certificates:
            return Finding("secure_boot", certificates[0], "secure_ca", {}, [certificates[1]], ["update"])
        return Finding("secure_boot", "ok", "secure_ok")
    # Riot Vanguard refuses to start on Windows 11 without them; others such as Battlefield's and Call of Duty's
    # anti-cheats need them too
    severity = "warning" if state["anti_cheat"] else "info"
    if certificates:
        items.append(certificates[1])
        severity = _worse(severity, certificates[0])
    return Finding("secure_boot", severity, "secure_off", {"n": len(items)}, items)


def check_windows_update(facts):
    settings = facts.get("update_settings")
    # The newest monthly update; the service's own date only if the servicing store cannot be read
    last = facts.get("windows_updated") or facts.get("last_update")
    if settings and settings["disabled"]:
        return Finding("windows_update", "problem", "wu_disabled", actions=["update"])
    # An update server of an organization (WSUS) and its policies are normal on a PC it manages. On any other PC
    # they are left by tools that block updates: a server on this PC itself answers nothing
    if settings and not _is_managed(facts):
        if settings.get("server"):
            severity = "problem" if LOCAL_SERVERS.search(settings["server"]) else "warning"
            return Finding("windows_update", severity, "wu_server", {"server": settings["server"]}, actions=["update"])
        if settings.get("blocked"):
            return Finding("windows_update", "warning", "wu_blocked", {"names": ", ".join(settings["blocked"])},
                           actions=["update"])
    if settings and settings["policy_off"]:
        return Finding("windows_update", "warning", "wu_policy", actions=["update"])
    paused = settings.get("paused_until") if settings else None
    if paused and paused > facts["now"] + datetime.timedelta(days=PAUSE_LIMIT_DAYS):
        return Finding("windows_update", "warning", "wu_paused", {"date": paused.date()}, actions=["update"])
    # Windows updates that failed to install again and again and have not been installed since, in this or a newer
    # version. Microsoft Store apps also update through this service, retry by themselves and are left out
    events = sorted(facts.get("update_events") or [], key=lambda e: e["time"])
    failed = {}
    for e in events:
        title = e["args"][0] if e["id"] == 19 and e["args"] else e["args"][1] if len(e["args"]) > 1 else ""
        if not title or STORE_APP.match(title):
            continue
        family = update_family(title)
        if family.startswith(UPDATE_FAMILIES_IGNORED):
            continue
        if e["id"] == 19:
            failed.pop(family, None)
        elif e["id"] == 20 and _error_code(e["args"][0]) not in UPDATE_ERRORS_IGNORED:
            count = failed.get(family, (None, None, 0))[2]
            failed[family] = (title, _error_code(e["args"][0]), count + 1)
    stuck = {title: code for title, code, count in failed.values() if count >= UPDATE_FAILURES}
    if last is None and not stuck:
        return unknown("windows_update")
    days = (facts["now"] - last).days if last else 0
    severity = "problem" if days >= 90 else "warning" if days >= 45 or stuck else "ok"
    params = {"date": last.date() if last else None}
    if stuck:
        items = [("item_update_failed", {"name": title, "code": code}) for title, code in list(stuck.items())[:6]]
        return Finding("windows_update", severity, "wu_failed", dict(params, n=len(stuck)), items, ["update"])
    return Finding("windows_update", severity, "wu_old" if severity != "ok" else "wu_ok", params, actions=["update"])


def update_family(title):
    """An update without its month, version and KB number: a newer one of the same kind replaces a failed one.
    "2026-10 Cumulative Update for Windows 11 (KB5127648)" -> "cumulative update for windows 11"."""
    title = re.sub(r"\([^)]*\)|\b\d{4}-\d{2}\b|\bKB\d+\b", " ", title)
    return " ".join(title.replace(" - ", " ").split()).lower()


def _error_code(value):
    """A Windows Update error as Windows shows it: 0x80070002."""
    try:
        return f"0x{int(value) & 0xFFFFFFFF:08X}"
    except (TypeError, ValueError):
        return value or "?"


def check_pending_restart(facts):
    pending = facts.get("restart_pending")
    if pending is None:
        return unknown("pending_restart")
    if pending:
        return Finding("pending_restart", "warning", "restart_pending", actions=["update"])
    return Finding("pending_restart", "ok", "restart_ok")


def check_windows_support(facts):
    info = facts.get("windows")
    if not info or not info["build"]:
        return unknown("windows_support")
    edition = info["edition"]
    if info["server"] or "EnterpriseS" in edition:
        return None  # LTSC and Server have their own, longer support
    build = info["build"]
    if build < 22000:
        version, home, long = SUPPORT_ENDS[19045]
    elif build in SUPPORT_ENDS:
        version, home, long = SUPPORT_ENDS[build]
    else:
        return None  # an Insider build or a version newer than this list: nothing reliable to say
    end = long if edition.startswith(LONG_EDITIONS) else home
    params = {"windows": f"{info['product']} {info['version'] or version}", "date": end}
    today = facts["now"].date()
    if build < 22000:  # Extended Security Updates may still cover it: that cannot be seen from here
        return Finding("windows_support", "warning", "support_win10", params, actions=["update"])
    if today > end:
        # Until the next monthly update is due nothing has been missed yet
        severity = "problem" if (today - end).days > 35 else "warning"
        return Finding("windows_support", severity, "support_ended", params, actions=["update"])
    if (end - today).days <= SUPPORT_WARN_DAYS:
        return Finding("windows_support", "warning", "support_ending", params, actions=["update"])
    return Finding("windows_support", "ok", "support_ok", params)


def check_network(facts):
    events = facts.get("events")
    if events is None:
        return unknown("network")
    since = _days_ago(facts, EVENT_DAYS)
    conflicts = [e for e in events if e["id"] == 4199 and e["provider"].lower() == "tcpip" and e["time"] >= since]
    if conflicts:
        last = max(conflicts, key=lambda e: e["time"])
        address = last["args"][1] if len(last["args"]) > 1 and last["args"][1] else "?"
        return Finding("network", "warning", "ip_conflict", {"address": address, "date": last["time"].date(),
                                                             "n": len(conflicts)}, actions=["network_status"])
    # A wired connection at 100 Mb/s or less: almost every network card and router does a gigabit, so the cable or
    # the port is at fault
    slow = [a for a in facts.get("adapters") or [] if 0 < (a.get("speed") or 0) <= 100_000_000]
    if slow:
        return Finding("network", "info", "ethernet_slow", {"name": slow[0].get("name") or "?",
                                                            "speed": (slow[0]["speed"] or 0) // 1_000_000},
                       actions=["network_status"])
    return Finding("network", "ok", "network_ok", {"days": EVENT_DAYS})


def check_proxy(facts):
    state = facts.get("proxy")
    if state is None:
        return unknown("proxy")
    if (state["enabled"] and state["server"]) or state["pac"]:
        return Finding("proxy", "warning", "proxy_on", {"server": state["server"] or state["pac"]},
                       actions=["proxy"])
    return Finding("proxy", "ok", "proxy_ok", actions=[])


def check_hosts(facts):
    state = facts.get("hosts")
    if state is None:
        return unknown("hosts")
    blocked = state["blocked"]
    if blocked:
        items = [("item_name", {"name": name}) for name in blocked[:10]]
        if len(blocked) > 10:
            items.append(("item_more", {"n": len(blocked) - 10}))
        return Finding("hosts", "warning", "hosts_blocks", {"n": len(blocked)}, items, ["hosts"])
    if state["entries"] >= HOSTS_MANY:
        return Finding("hosts", "info", "hosts_many", {"n": state["entries"]}, actions=["hosts"])
    return Finding("hosts", "ok", "hosts_ok", {"n": state["entries"]})


def check_crash_files(facts):
    found = facts.get("crash_files")
    if found is None:
        return unknown("crash_files")
    recent = sorted((f for f in found if f["recent"]), key=lambda f: (-f["recent"], f["name"]))
    if not recent:
        return Finding("crash_files", "ok", "crash_files_ok", {"days": CRASH_FILE_DAYS})
    items = [("item_crash_files", {"name": f["name"], "n": f["recent"], "date": f["newest"].date(), "folder": f["folder"]})
             for f in recent[:8]]
    items.append(("item_crash_files_hidden", {}))
    if any(f["kind"] == "crashpad" for f in recent):
        items.append(("item_crash_files_tabs", {}))
    severity = "warning" if recent[0]["recent"] >= 3 else "info"
    actions = ["reliability"] if any(f["kind"] == "wer" for f in recent) else []
    return Finding("crash_files", severity, "crash_files", {"n": sum(f["recent"] for f in recent),
                                                            "days": CRASH_FILE_DAYS, "name": recent[0]["name"]},
                   items, actions)


def check_live_kernel(facts):
    live = facts.get("live_kernel")
    if live is None:
        return unknown("live_kernel")
    if not live["readable"]:
        if live["components"]:
            return Finding("live_kernel", "info", "live_kernel_registry", {"components": ", ".join(live["components"])})
        return unknown("live_kernel", "unknown_admin")
    since = _days_ago(facts, LIVE_KERNEL_DAYS)
    recent = [d for d in live["dumps"] if d["time"] >= since]
    if not recent:
        if live["dumps"]:
            return Finding("live_kernel", "ok", "live_kernel_old",
                           {"days": LIVE_KERNEL_DAYS, "date": max(d["time"] for d in live["dumps"]).date()})
        return Finding("live_kernel", "ok", "live_kernel_ok", {"days": LIVE_KERNEL_DAYS})
    kinds = {}
    for dump in recent:
        component = dump["component"] or "LiveKernelReports"
        kind = LIVE_KERNEL_KINDS.get(component.lower(), "kind_live_other")
        entry = kinds.setdefault(kind, {"component": component, "n": 0, "date": dump["time"]})
        entry["n"] += 1
        entry["date"] = max(entry["date"], dump["time"])
    items = [("item_live_kind", {"kind": Text(kind), "component": v["component"], "n": v["n"], "date": v["date"].date()})
             for kind, v in sorted(kinds.items(), key=lambda item: -item[1]["n"])]
    items += [(LIVE_KERNEL_HINTS[kind], {}) for kind in kinds if kind in LIVE_KERNEL_HINTS]
    if facts.get("wer_off"):
        items.append(("item_wer_off", {}))
    return Finding("live_kernel", "warning", "live_kernel", {"n": len(recent), "days": LIVE_KERNEL_DAYS}, items,
                   ["devices", "reliability"])


def _version_tuple(text):
    parts = re.findall(r"\d+", str(text or ""))
    return tuple(int(p) for p in parts[:4])


def check_conflicting_software(facts):
    found = facts.get("software")
    if found is None:
        return unknown("conflicting_software")
    installed, watched = found.get("programs") or {}, found.get("services") or {}
    running = facts.get("processes") or set()
    items, severities, actions = [], [], []

    def program(*fragments):
        for key, (title, version) in installed.items():
            if any(fragment in key for fragment in fragments):
                return title, version
        return None

    def service(*fragments):
        for name, info in watched.items():
            if any(fragment in f"{name} {info.get('display') or ''}".lower() for fragment in fragments):
                return name, info
        return None

    def add(key, severity, params=None, action=None):
        items.append((key, params or {}))
        severities.append(severity)
        if action and action not in actions:
            actions.append(action)

    inpout = service("inpoutx64")
    if inpout and inpout[1].get("start") != 4:
        add("item_sw_inpout", "warning", action="devices")
    nahimic = service("nahimic", "a-volute")
    if nahimic:
        name, info = nahimic[1].get("display") or nahimic[0], nahimic[1]
        active = nahimic[0] in running or info.get("start") == 2
        add("item_sw_nahimic" if active else "item_sw_nahimic_installed", "warning" if active else "info",
            {"name": name}, "services")
    else:
        for package in found.get("packages") or []:
            lowered = package.lower()
            name = "Sonic Studio" if "sonicstudio" in lowered else "Sonic Radar" if "sonicradar" in lowered else "Nahimic"
            if not any(p.get("name") == name for _, p in items):
                add("item_sw_nahimic_installed", "info", {"name": name}, "apps")
    killer = service("killer", "rivet")
    if killer:
        add("item_sw_killer", "info", {"name": killer[1].get("display") or killer[0]}, "apps")
    cfos = service("cfosspeed")
    if cfos:
        add("item_sw_cfos", "info", {"name": cfos[1].get("display") or cfos[0]}, "apps")
    overwolf = program("overwolf")
    if overwolf:
        rtss = found.get("rtss")
        if rtss and tuple(rtss[:3]) < RTSS_FIXED:
            add("item_sw_overwolf_rtss", "warning", {"version": ".".join(str(p) for p in rtss[:3])}, "apps")
        capture = program("obs studio", "nvidia app")
        if capture:
            add("item_sw_overwolf_capture", "info", {"name": capture[0]}, "apps")
    machine = program("vmware workstation", "vmware player")
    if machine and (facts.get("vbs") or {}).get("running"):
        add("item_sw_vmware_vbs", "info", {"name": machine[0]}, "core_isolation")
    for fragment in PUP_PROGRAMS:
        pup = program(fragment)
        if pup:
            add("item_sw_pup", "warning", {"name": pup[0]}, "apps")
    scam = program(*SCAM_PROGRAMS)
    if scam:
        add("item_sw_scam", "warning", {"name": scam[0]}, "apps")
    for fragment in OPTIMIZER_PROGRAMS:
        optimizer = program(fragment)
        if optimizer:
            add("item_sw_optimizer", "info", {"name": optimizer[0]}, "apps")
    if any(key.startswith("ccleaner") and "browser" not in key for key in installed):
        add("item_sw_ccleaner", "info", action="apps")
    arc = any(pci_vendor(c.get("pnp")) == INTEL and re.search(r"\bArc\b", c.get("name") or "")
              for c in facts.get("video") or [])
    if arc and (program("armoury crate") or service("armourycrate")):
        add("item_sw_armoury_arc", "warning", action="apps")
    if program("corsair link") and program("icue"):
        add("item_sw_corsair_link", "info", action="apps")
    gaming_software, hub = program("logitech gaming software"), program("logitech g hub", "g hub")
    if gaming_software and hub and _version_tuple(gaming_software[1])[:2] < LGS_FIXED:
        add("item_sw_lgs_ghub", "info", {"version": gaming_software[1] or "?"}, "apps")
    if not items:
        return Finding("conflicting_software", "ok", "conflicts_ok", {})
    severity = min(severities, key=SEVERITIES.index)
    return Finding("conflicting_software", severity, "conflicts", {"n": len(items)}, items, actions)


def _worse(severity, other):
    return min(severity, other, key=SEVERITIES.index)


def _number(data, key):
    value = (data.get(key) or "").strip()
    return int(value) if value.isdigit() else 0


def check_video_memory(facts):
    events = facts.get("perf_events")
    if events is None:
        return None  # only administrators may read this log, and running short is rare: nothing to point out
    since = _days_ago(facts, EVENT_DAYS)
    # Scenario 2 of the desktop window manager: "video memory resources are over-utilized and there is thrashing"
    short = [e for e in events if e["id"] in (500, 501) and e["data"].get("Scenario") == "2" and e["time"] >= since]
    if len(short) < VIDEO_MEMORY_EVENTS:
        return None
    last = max(short, key=lambda e: e["time"])
    return Finding("video_memory", "info", "vram_short", {"n": len(short), "days": EVENT_DAYS, "date": last["time"].date(),
                                                          "name": last["data"].get("DisplayDeviceFriendlyName") or "?"},
                   actions=["taskmgr"])


# Events of Diagnostics-Performance that name what slowed a start or a shutdown down. Programs (101) are left out:
# Windows names everything that started right after sign-in, a program opened by hand too; their cost at the start
# comes from the startup measurements instead
SLOW_CULPRITS = {102: "driver", 103: "service", 109: "device", 202: "shutdown_device", 203: "shutdown_service",
                 201: "shutdown_app"}


def check_boot_time(facts):
    events = facts.get("perf_events")
    if events is None:
        return unknown("boot_time", "unknown_admin" if facts.get("admin") is False else "unknown_read")
    starts = [e for e in events if e["id"] == 100 and e["data"].get("BootIsRebootAfterInstall", "").lower() != "true"
              and _number(e["data"], "BootTime")]
    if not starts:
        # The Diagnostic Policy Service writes these events; without it there are none to read
        if any(service[0] == "DPS" for service in facts.get("disabled_services") or []):
            return unknown("boot_time", "unknown_dps")
        return None
    times = sorted(_number(e["data"], "BootTime") for e in starts)
    params = {"seconds": round(times[len(times) // 2] / 1000), "n": len(times)}
    found = {}
    for e in events:
        kind = SLOW_CULPRITS.get(e["id"])
        if not kind:
            continue
        name = e["data"].get("FriendlyName") or e["data"].get("Name") or "?"
        entry = found.setdefault((kind, name), {"starts": set(), "delays": []})
        # A start's culprits are written together with it, in the same minute
        entry["starts"].add(e["time"].replace(second=0, microsecond=0))
        entry["delays"].append(_number(e["data"], "DegradationTime"))
    slow = []
    for (kind, name), entry in found.items():
        delays = sorted(entry["delays"])
        typical = delays[len(delays) // 2]
        if len(entry["starts"]) >= SLOW_STARTS and typical >= SLOW_START_MS:
            slow.append((kind, name, typical, len(entry["starts"])))
    if not slow:
        return Finding("boot_time", "ok", "boot_time_ok", params)
    slow.sort(key=lambda s: -s[2])
    items = [("item_slow_" + kind, {"name": name, "seconds": round(delay / 1000, 1), "n": n})
             for kind, name, delay, n in slow[:6]]
    total = sum(delay for kind, _, delay, _ in slow)
    actions = (["devices"] if any(s[0] in ("driver", "device", "shutdown_device") for s in slow) else []) + \
              (["services"] if any(s[0] in ("service", "shutdown_service") for s in slow) else [])
    return Finding("boot_time", "warning" if total >= SLOW_START_TOTAL_MS else "info", "boot_slowed",
                   dict(params, names=", ".join(dict.fromkeys(name for _, name, _, _ in slow[:3]))), items, actions)


def check_xbox_network(facts):
    setup = facts.get("network_setup")
    if setup is None:
        return unknown("xbox_network")
    ipv6 = setup["ipv6"] & 0xFFFFFFFF
    items, severity = [], "ok"
    if ipv6 == IPV6_DELAY:
        items.append(("item_ipv6_delay", {}))
        severity = "warning"
    if setup["gaming"]:
        # Xbox party chat and many multiplayer games connect through Teredo, which runs in the IP Helper service
        if facts.get("teredo") == TEREDO_DISABLED or setup["teredo_policy_off"] or ipv6 & IPV6_TUNNELS_OFF:
            items.append(("item_teredo_off", {}))
            severity = "warning"
        if setup["ip_helper_off"]:
            items.append(("item_ip_helper_off", {}))
            severity = "warning"
        # Services merged into shared processes (a threshold raised above the memory): Xbox controllers and the
        # Game Bar stop working. The default (3.5 GB) merges them on PCs with less memory by design
        memory = (facts.get("memory") or {}).get("total") or 0
        if setup["split"] not in (None, SVCHOST_DEFAULT) and memory and setup["split"] * 1024 >= memory:
            items.append(("item_svchost_merged", {}))
            severity = "warning"
    # 0x20 only prefers IPv4, which Microsoft supports; the other bits turn parts of IPv6 off
    if ipv6 & ~0x20 and ipv6 != IPV6_DELAY and not items:
        items.append(("item_ipv6_off", {}))
        severity = "info"
    if not items:
        return Finding("xbox_network", "ok", "xbox_ok")
    return Finding("xbox_network", severity, "xbox_changed", {"n": len(items)}, items, ["network_status"])


def check_drive_link(facts):
    links = facts.get("drive_links")
    if not links:
        return None  # no NVMe drive, or its link could not be read
    names = {d.get("id"): d.get("name") or "?" for d in facts.get("disks") or []}
    items, severity, slow = [], "ok", None
    for number, (speed, width, top_speed, top_width) in sorted(links.items()):
        params = {"name": names.get(number, "?"), "speed": speed, "width": width, "max_speed": top_speed,
                  "max_width": top_width}
        if width < top_width:  # half its lanes: a slot shared with another device, or an adapter
            items.append(("item_link_narrow", params))
            severity, slow = "warning", slow or params
        elif speed < top_speed:  # the slot or the board is an older generation
            items.append(("item_link_slower", params))
            severity, slow = _worse(severity, "info"), slow or params
        else:
            items.append(("item_link_full", params))
    if slow:
        return Finding("drive_link", severity, "drive_link_slow", slow, items)
    return Finding("drive_link", "ok", "drive_link_ok", {}, items)


VOLUME_HEALTH = {1: ("item_volume_scan", "info"), 2: ("item_volume_fix", "warning"),
                 3: ("item_volume_repair", "problem")}  # MSFT_Volume.HealthStatus


def check_volume_health(facts):
    volumes = facts.get("volumes")
    if volumes is None:
        return unknown("volume_health", "unknown_admin" if facts.get("admin") is False else "unknown_read")
    dirty = {d.rstrip(":").upper() for d in facts.get("dirty") or []}
    items, severity = [], "ok"
    for volume in sorted(volumes, key=lambda v: v.get("drive") or ""):
        drive = (volume.get("drive") or "").rstrip(":").upper()
        if not drive:
            continue
        if volume.get("health") in VOLUME_HEALTH:
            key, level = VOLUME_HEALTH[volume["health"]]
            items.append((key, {"drive": drive + ":"}))
            severity = _worse(severity, level)
        elif drive in dirty:  # Windows checks the drive at the next start
            items.append(("item_volume_dirty", {"drive": drive + ":"}))
            severity = _worse(severity, "warning")
    if not items:
        return Finding("volume_health", "ok", "volumes_ok", {"n": len(volumes)})
    return Finding("volume_health", severity, "volumes_damaged", {"n": len(items)}, items)


def check_app_platform(facts):
    state, info = facts.get("app_platform"), facts.get("windows") or {}
    if info.get("server"):
        return None  # Windows Server comes without most of these
    if state is None:
        return unknown("app_platform")
    edition, build = info.get("edition") or "", info.get("build") or 0
    packages, removed = state["packages"], state["deprovisioned"]

    def has(prefixes):
        return any(p.startswith(prefixes) for p in packages)

    found = []
    store = not edition.startswith(NO_STORE_EDITIONS)
    if store and not has(STORE_PACKAGE):
        found.append(("item_no_store", STORE_PACKAGE, "warning"))
    if not has(SECURITY_APP_PACKAGES):
        found.append(("item_no_security_app", SECURITY_APP_PACKAGES[0], "warning"))
    if build >= 22000 and not has(SHELL_PACKAGE):
        found.append(("item_no_shell", SHELL_PACKAGE, "warning"))
    if store and not has(APP_INSTALLER_PACKAGE):
        found.append(("item_no_app_installer", APP_INSTALLER_PACKAGE, "info"))
    if state["gaming"] and not has(XBOX_IDENTITY_PACKAGE):
        found.append(("item_no_xbox_identity", XBOX_IDENTITY_PACKAGE, "warning"))
    if not state["webview2"]:
        # Windows 11 comes with it; on Windows 10 it arrives with Edge and Microsoft 365
        found.append(("item_no_webview2", None, "warning" if build >= 22000 else "info"))
    if not found:
        return Finding("app_platform", "ok", "platform_ok")
    items = []
    for key, prefix, _ in found:
        items.append((key, {}))
        if prefix and any(name.startswith(prefix) for name in removed):
            items.append(("item_removed_for_all", {}))
    severity = min((f[2] for f in found), key=SEVERITIES.index)
    return Finding("app_platform", severity, "platform_missing", {"n": len(found)}, items)


def check_wmi_health(facts):
    code, repository = facts.get("wmi"), facts.get("wmi_repository")
    if repository:  # Windows' own check of the repository found it inconsistent
        return Finding("wmi_health", "problem", "wmi_damaged", {"code": f"0x{repository:08X}"})
    if code:
        return Finding("wmi_health", "warning", "wmi_error", {"code": f"0x{code & 0xFFFFFFFF:08X}"})
    if code is None and repository is None:
        return unknown("wmi_health")
    return Finding("wmi_health", "ok", "wmi_ok")


def _subject_name(subject):
    found = re.search(r"CN=([^,]+)", subject or "")
    return (found.group(1) if found else subject or "?").strip().strip('"')


BLOCKED_ORDER = ("sign_in", "hijack", "protection", "windows")


def check_blocked_tools(facts):
    state = facts.get("blocked")
    if state is None:
        return unknown("blocked_tools")
    items, severity, count = [], "ok", 0
    for found in sorted(state["programs"], key=lambda p: (BLOCKED_ORDER.index(p["kind"]), p["program"])):
        debugger = os.path.basename(command_program(found["debugger"])) or found["debugger"]
        items.append(("item_blocked_" + found["kind"], {"name": found["program"], "debugger": debugger}))
        items += [("item_blocked_service", {"name": service}) for service in found["services"]]
        severity = _worse(severity, "info" if found["kind"] == "windows" else "warning")
        count += 1
    # Locks a school or a workplace sets on purpose are worth knowing about only
    lock_level = "info" if _is_managed(facts) else "warning"
    for tool in state["locks"]:
        items.append(("item_lock_" + tool, {}))
        severity, count = _worse(severity, lock_level), count + 1
    if state["disallowed"]:
        items.append(("item_lock_names", {"names": ", ".join(state["disallowed"][:6])}))
    for name in state["firewall"]:
        items.append(("item_firewall_block", {"name": name}))
        severity, count = _worse(severity, "warning"), count + 1
    vendors = list(dict.fromkeys(_subject_name(s) for s in facts.get("disallowed") or [] if SECURITY_VENDORS.search(s)))
    for name in vendors[:5]:
        items.append(("item_untrusted_vendor", {"name": name}))
        severity, count = _worse(severity, "warning"), count + 1
    if not items:
        return Finding("blocked_tools", "ok", "blocked_ok")
    if state["locks"] and lock_level == "info":
        items.append(("item_managed", {}))
    return Finding("blocked_tools", severity, "blocked_protection" if severity == "warning" else "blocked_windows",
                   {"n": count}, items)


def check_recovery_env(facts):
    if (facts.get("windows") or {}).get("server"):
        return None
    state = facts.get("recovery")
    if state is None:
        return unknown("recovery_env")
    if state["enabled"]:
        return Finding("recovery_env", "ok", "recovery_ok")
    return Finding("recovery_env", "warning", "recovery_off", actions=["recovery"])


def check_time_sync(facts):
    events = facts.get("time_events")
    if events is None:
        return unknown("time_sync")
    week = _days_ago(facts, 7)
    # Event 36: none of the time sources gave a usable time for a while; 35 and 37 are successful syncs
    stuck = [e for e in events if e["id"] == 36 and e["time"] >= week]
    synced = [e for e in events if e["id"] in (35, 37)]
    if stuck and not any(e["time"] > max(s["time"] for s in stuck) for e in synced):
        return Finding("time_sync", "warning", "time_stuck", {"date": max(e["time"] for e in stuck).date()},
                       actions=["date_time"])
    if synced:
        return Finding("time_sync", "ok", "time_ok", {"date": max(e["time"] for e in synced).date()})
    return Finding("time_sync", "ok", "time_quiet", {"days": TIME_DAYS})


def check_defender(facts):
    defender = facts.get("defender")
    if not defender or not defender["mode"].lower().startswith("normal"):
        return None  # another antivirus is at work, or Defender is not there: the antivirus check tells which
    exclusions, threats = facts.get("defender_exclusions"), facts.get("threats")
    if exclusions is None and threats is None:
        return unknown("defender", "unknown_admin" if facts.get("admin") is False else "unknown_read")
    items, severity = [], "ok"
    for threat in threats or []:
        name = threat.get("name") or "?"
        if HOSTS_THREAT.search(name):  # an edited hosts file: the hosts check looks at what it blocks
            items.append(("item_threat_hosts", {"name": name}))
            severity = _worse(severity, "info")
        else:
            items.append(("item_threat", {"name": name}))
            severity = _worse(severity, "problem" if (threat.get("severity") or 0) >= 4 else "warning")
    broad = []
    for kind in ("paths", "extensions", "processes"):
        for value in (exclusions or {}).get(kind) or []:
            if broad_exclusion(kind, value):
                broad.append(value)
    items += [("item_exclusion_broad", {"name": value}) for value in broad[:8]]
    if broad:
        severity = _worse(severity, "info" if _is_managed(facts) else "warning")
    if not defender["tamper"] and not _is_managed(facts):
        items.append(("item_tamper_off", {}))
        severity = _worse(severity, "warning")
    total = sum(len((exclusions or {}).get(kind) or []) for kind in ("paths", "extensions", "processes"))
    if total > len(broad):
        items.append(("item_exclusions", {"n": total}))
        severity = _worse(severity, "info")
    if severity == "ok":
        return Finding("defender", "ok", "defender_ok", actions=["security"])
    line = "defender_threats" if any(key == "item_threat" for key, _ in items) else \
        "defender_weakened" if severity == "warning" else "defender_notes"
    return Finding("defender", severity, line, {"n": len(items)}, items, ["security"])


def check_browser_policies(facts):
    found = facts.get("browser_policies")
    if found is None:
        return unknown("browser_policies")
    if not found:
        return Finding("browser_policies", "ok", "browser_ok")
    items = [("item_policy_" + f["kind"], {"browser": f["browser"], "value": f["value"]}) for f in found[:8]]
    if _is_managed(facts):
        return Finding("browser_policies", "info", "browser_forced", {"n": len(found)},
                       items + [("item_managed", {})])
    return Finding("browser_policies", "warning", "browser_forced", {"n": len(found)}, items)


def check_root_certificates(facts):
    found = facts.get("added_roots")
    if found is None:
        return unknown("root_certificates")
    if not found:
        return Finding("root_certificates", "ok", "roots_ok")
    items = [("item_root_user" if f["user"] else "item_root", {"name": f["name"]}) for f in found[:8]]
    return Finding("root_certificates", "info", "roots_added", {"n": len(found)}, items)


def check_accounts(facts):
    users, settings = facts.get("local_users"), facts.get("account_settings")
    if users is None and settings is None:
        return unknown("accounts")
    managed_pc = _is_managed(facts)
    items, severity = [], "ok"
    enabled = {u.get("name", "").lower(): u for u in users or [] if u.get("enabled")}
    for user in enabled.values():
        rid = (user.get("sid") or "").rpartition("-")[2]
        if rid == "501":
            items.append(("item_guest_on", {"name": user.get("name") or "?"}))
            severity = _worse(severity, "warning")
        elif rid == "500":
            items.append(("item_builtin_admin_on", {"name": user.get("name") or "?"}))
            severity = _worse(severity, "info" if managed_pc else "warning")
    for name in (settings or {}).get("hidden") or []:
        if name.lower() in enabled:  # an account in use that the sign-in screen does not show
            items.append(("item_account_hidden", {"name": name}))
            severity = _worse(severity, "warning")
    if (settings or {}).get("autologon_password"):
        items.append(("item_autologon_password", {}))
        severity = _worse(severity, "warning")
    if not items:
        return Finding("accounts", "ok", "accounts_ok")
    return Finding("accounts", severity, "accounts_risky", {"n": len(items)}, items, ["accounts"])


def check_network_exposure(facts):
    firewall, desktop = facts.get("firewall"), facts.get("remote_desktop")
    if firewall is None and desktop is None:
        return unknown("network_exposure")
    items, severity = [], "ok"
    # Profiles turned off, unless another firewall registered with Security Center does the job. The domain profile
    # applies only to PCs in a domain
    others = [name for name in facts.get("firewall_products") or [] if "windows" not in name.lower()]
    profiles = ["private", "public"] + (["domain"] if (facts.get("managed") or {}).get("domain") else [])
    off = [p for p in profiles if firewall and firewall.get(p) is False]
    if off and not others:
        items += [("item_firewall_off_" + p, {}) for p in off]
        severity = _worse(severity, "problem" if "public" in off else "warning")
    if facts.get("smb1"):
        items.append(("item_smb1", {}))
        severity = _worse(severity, "warning" if any("server" in name.lower() for name in facts["smb1"]) else "info")
    if desktop and desktop["on"]:
        items.append(("item_rdp_nla_off" if desktop["nla_off"] else "item_rdp_on", {}))
        severity = _worse(severity, "warning" if desktop["nla_off"] else "info")
    if desktop and desktop["wrapper"]:
        items.append(("item_rdp_wrapper", {}))
        severity = _worse(severity, "info")
    if not items:
        return Finding("network_exposure", "ok", "exposure_ok", actions=["firewall"])
    return Finding("network_exposure", severity, "exposure_open", {"n": len(items)}, items, ["firewall"])


def check_remote_tools(facts):
    software_found = facts.get("software")
    if software_found is None:
        return None
    names = []
    for title, _ in software_found["programs"].values():
        for pattern, name in REMOTE_TOOLS:
            if pattern.search(title) and name not in names:
                names.append(name)
    if not names:
        return None  # nothing to point out
    return Finding("remote_tools", "info", "remote_installed", {"names": ", ".join(names)}, actions=["apps"])


def check_bitlocker(facts):
    state = facts.get("bitlocker")
    if state is None:
        return unknown("bitlocker", "unknown_admin" if facts.get("admin") is False else "unknown_read")
    conversion, protection, keys = state.get("conversion"), state.get("protection"), state.get("recovery") or []
    if conversion in (None, 0):
        return Finding("bitlocker", "ok", "bitlocker_off")
    # Encrypted without protection: device encryption waiting for a Microsoft account, or BitLocker suspended
    if protection != 1:
        return Finding("bitlocker", "info", "bitlocker_suspended", actions=["encryption"])
    if not keys:
        return Finding("bitlocker", "warning", "bitlocker_no_key", actions=["encryption"])
    key_id = keys[0].strip("{}")[:8].upper()
    return Finding("bitlocker", "info", "bitlocker_key", {"id": key_id}, actions=["encryption"])


VERDICTS = {check: globals()["check_" + check] for check, _ in CHECKS}


def evaluate(facts):
    """Findings of every check that applies to this PC, in the order of CHECKS."""
    findings = []
    for check, _ in CHECKS:
        try:
            finding = VERDICTS[check](facts)
        except Exception:  # odd data from one source must not hide the other findings
            finding = unknown(check)
        if finding is not None:
            findings.append(finding)
    return findings


def counts(findings):
    """{severity: how many findings have it}"""
    result = dict.fromkeys(SEVERITIES, 0)
    for finding in findings:
        result[finding.severity] += 1
    return result
