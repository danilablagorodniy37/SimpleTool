"""Troubleshooting: looks for common causes of slowdowns, crashes and conflicts on this PC.

Everything here only reads: memory and processor counters, drives, the registry, the hosts file, the Windows event
logs and a few system lists through PowerShell. Nothing is changed and nothing leaves the PC.

gather() collects facts, evaluate() turns them into findings. They are separate so the tests can check every
verdict on made-up facts. A fact that could not be read is missing, and its check says so instead of guessing.
"""
import ctypes
import datetime
import json
import os
import re
import subprocess
import time
import uuid
import winreg
from ctypes import wintypes

import engine
import limiter
import services
import sysinfo

GROUPS = ["performance", "storage", "stability", "security"]
# (check, group) in the order they are shown
CHECKS = [
    ("ram_load", "performance"), ("ram_size", "performance"), ("memory_config", "performance"),
    ("kernel_memory", "performance"), ("pagefile", "performance"), ("cpu_load", "performance"),
    ("cpu_microcode", "performance"), ("x3d_cores", "performance"), ("power_plan", "performance"),
    ("graphics_driver", "performance"), ("display_output", "performance"), ("gpu_link", "performance"),
    ("gpu_preference", "performance"), ("refresh_rate", "performance"), ("startup_apps", "performance"),
    ("rgb_software", "performance"), ("game_dvr", "performance"), ("boot_options", "performance"),
    ("throttling", "performance"), ("uptime", "performance"),
    ("disk_space", "storage"), ("disk_health", "storage"), ("system_drive", "storage"), ("disk_errors", "storage"),
    ("temp_files", "storage"),
    ("crashes", "stability"), ("app_crashes", "stability"), ("gpu_resets", "stability"), ("whea", "stability"),
    ("memory_test", "stability"), ("devices", "stability"), ("services", "stability"),
    ("core_services", "stability"), ("system_files", "stability"), ("vc_runtime", "stability"),
    ("media_pack", "stability"), ("battery", "stability"),
    ("antivirus", "security"), ("security_settings", "security"), ("memory_integrity", "security"),
    ("secure_boot", "security"), ("windows_update", "security"), ("pending_restart", "security"),
    ("windows_support", "security"), ("network", "security"), ("proxy", "security"), ("hosts", "security"),
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
    "network_status": ("open", "ms-settings:network-status", None),
    "proxy": ("open", "ms-settings:network-proxy", None),
    "hosts": ("open", "notepad.exe", "%HOSTS%"),
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
                      "max_mhz1": "75b0ae3f-bce0-45a7-8c89-c9611c25e101"}

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
               ("ntfs", 55): "ntfs", ("ntfs", 50): "write"}
DISK_SERIOUS = ("bad_block", "controller", "paging", "ntfs", "write")
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
                 ("msiserver", "install"), ("AppXSvc", "install"), ("ClipSVC", "install"), ("InstallService", "install"),
                 ("Audiosrv", "sound"), ("AudioEndpointBuilder", "sound"), ("BFE", "firewall"), ("mpssvc", "firewall"),
                 ("EventLog", "logs"), ("Winmgmt", "logs"), ("Schedule", "tasks"), ("Dhcp", "network"),
                 ("Dnscache", "network"), ("W32Time", "clock")]
# Disabled, these only take a feature away: noted, not a problem
OPTIONAL_SERVICES = [("XblAuthManager", "xbox"), ("XboxGipSvc", "xbox"), ("GamingServices", "xbox"),
                     ("WSearch", "search"), ("WerSvc", "reports")]
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


def cpu(api, seconds=CPU_SAMPLE):
    """Processor load over a short interval and the programs that used it: {"load": %, "top": [(name, %)]}.
    SimpleTool itself is left out of the programs."""
    start = _system_times()
    processes = [(pid, name) for pid, name in api.processes() if pid not in (0, os.getpid())]
    before = {pid: api.cpu_time(pid) for pid, _ in processes}
    time.sleep(seconds)
    end = _system_times()
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
    return {"load": max(0.0, min(100.0, load)), "top": [item for item in top if item[1] >= 1][:5]}


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
    """{"size": bytes, "partial": whether the time ran out first}. Links are not followed."""
    size, stack, deadline = 0, [path], time.monotonic() + budget
    while stack:
        if time.monotonic() > deadline:
            return {"size": size, "partial": True}
        try:
            with os.scandir(stack.pop()) as entries:
                for entry in entries:
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            stack.append(entry.path)
                        elif entry.is_file(follow_symlinks=False):
                            size += entry.stat(follow_symlinks=False).st_size
                    except OSError:
                        continue
        except OSError:
            continue
    return {"size": size, "partial": False}


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
    """Whether the Windows Update service is disabled or automatic updates are turned off by a policy."""
    return {"disabled": _read(r"HKLM\SYSTEM\CurrentControlSet\Services\wuauserv", "Start") == 4,
            "policy_off": _read(r"HKLM\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU", "NoAutoUpdate") == 1}


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
    return {"uefi": uefi, "secure_boot": None if secure is None else secure == 1, "tpm": tpm,
            "anti_cheat": anti_cheat}


def security_settings():
    """Protections that "optimization" tools turn off: UAC, and the Spectre and Meltdown mitigations."""
    return {"uac_off": _read(r"HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System", "EnableLUA") == 0,
            "mitigations_off": _read(MEMORY_MANAGEMENT, "FeatureSettingsOverride") == 3 and
            _read(MEMORY_MANAGEMENT, "FeatureSettingsOverrideMask") == 3}


# One PowerShell run for what has no simple Windows call: drives' health, devices with problems, antivirus, the
# processor and memory modules, network adapters, battery wear and the event logs. Each part fails on its own and is
# then missing. Logs that can fill up with one kind of event are read on their own, so a flood of one does not push
# the others out; drive events are filtered with XPath, which does not fail on a driver this PC does not have
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
       "throttle_days": THROTTLE_DAYS, "disk_providers": "', '".join(DISK_PROVIDERS)}

EVENT_KEYS = ("events", "disk_events", "nvidia_events", "throttle_events", "shutdowns", "service_events",
              "update_events", "memory_tests", "live_events", "whea", "app_events")


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
    read("game_dvr", game_dvr)
    read("boot", boot_options)
    read("uptime", uptime)
    read("fast_startup", fast_startup)
    read("graphics", sysinfo.graphics)
    if X3D_DUAL.search((facts.get("processor") or {}).get("name", "")):
        read("x3d", x3d_support)
        read("game_bar", game_bar)
    report("performance")
    read("drives", drives)
    read("system_disk", system_disk)
    read("trim_off", trim_off)
    read("temp", lambda: folder_size(temp_dir()) if temp_dir() else None)
    if process:
        try:
            facts.update(finish_powershell(process))
        except OSError:
            pass
    # The PCI Express lanes of the graphics cards, known now that PowerShell has named them
    read("links", lambda: {v.get("name"): pcie_width(v["pnp"]) for v in facts.get("video") or []
                           if pci_vendor(v.get("pnp"))})
    report("storage")
    read("disabled_services", disabled_services)
    read("wer_off", wer_off)
    read("vc_runtime", vc_runtime)
    report("stability")
    read("restart_pending", restart_pending)
    read("update_settings", update_settings)
    read("windows_updated", last_windows_update)
    read("windows", windows)
    read("firmware", firmware)
    read("security", security_settings)
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
    severity = "warning" if load >= 80 else "ok"
    items = [("item_program_percent", {"name": name, "percent": round(share)}) for name, share in sample["top"]]
    return Finding("cpu_load", severity, "cpu_high" if severity != "ok" else "cpu_ok", {"percent": load}, items,
                   ["taskmgr"])


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
    if plugged and state["scheme"] == POWER_SAVER:
        return Finding("power_plan", "warning", "power_saver", params, actions=["power"])
    if plugged and state["overlay"] == OVERLAY_EFFICIENCY:
        return Finding("power_plan", "warning", "power_efficiency", params, actions=["power_mode"])
    if plugged:
        caps = [state.get(key) for key in ("max_cpu", "max_cpu1") if state.get(key) is not None]
        if caps and min(caps) < 100:
            return Finding("power_plan", "warning", "power_capped", dict(params, percent=min(caps)), actions=["power"])
        if state.get("boost") == 0:
            return Finding("power_plan", "warning", "boost_off", params, actions=["power"])
        mhz = [state.get(key) for key in ("max_mhz", "max_mhz1") if state.get(key)]
        if mhz:
            return Finding("power_plan", "warning", "freq_capped", dict(params, mhz=min(mhz)), actions=["power"])
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
    severity = "warning" if len(names) > 10 else "ok"
    items = [("item_name", {"name": name}) for name in sorted(names, key=str.lower)]
    return Finding("startup_apps", severity, "startup_many" if severity != "ok" else "startup_ok", {"n": len(names)},
                   items, ["startup"])


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
    # Wear and uncorrected read errors: only administrators can read them, and some drives leave them empty
    counters = {c.get("id"): c for c in facts.get("wear") or []}
    items = []
    for d in disks:
        params = {"name": d.get("name") or "?", "media": d.get("media") or "?", "bus": d.get("bus") or "?",
                  "health": _health(d)}
        wear = counters.get(d.get("id"), {}).get("wear")
        items.append(("item_disk_wear", dict(params, wear=wear)) if isinstance(wear, int) else ("item_disk", params))
    # "Unknown" comes from USB bridges, RAID and virtual disks: no data rather than a fault
    bad = [d for d in disks if (d.get("health") or "").lower() in ("warning", "unhealthy")]
    if bad:
        severity = "problem" if any(d["health"].lower() == "unhealthy" for d in bad) else "warning"
        return Finding("disk_health", severity, "health_bad", {"name": bad[0].get("name") or "?",
                                                               "health": _health(bad[0])}, items)
    for d in disks:
        counter = counters.get(d.get("id"), {})
        wear, errors = counter.get("wear"), counter.get("read_errors")
        params = {"name": d.get("name") or "?", "wear": wear}
        if isinstance(wear, int) and wear >= 90:
            return Finding("disk_health", "problem" if wear >= 100 else "warning", "ssd_worn", params, items)
        if isinstance(errors, int) and errors > 0:
            return Finding("disk_health", "warning", "read_errors", dict(params, n=errors), items)
    return Finding("disk_health", "ok", "health_ok", {}, items)


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
        # "\Device\Harddisk2\DR2": errors of a memory stick or card pulled out are normal
        disk = re.search(r"Harddisk(\d+)", e["args"][0] if e["args"] else "")
        removable = provider == "disk" and disk is not None and buses.get(disk.group(1)) in REMOVABLE_BUSES
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
    params = {"size": Size(temp["size"])}
    line = "temp_size_partial" if temp["partial"] else "temp_size"
    severity = "warning" if temp["size"] >= 5 * GB else "ok"
    return Finding("temp_files", severity, line, params, actions=["temp", "storage"] if severity != "ok" else [])


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
        items.append(("item_bsod", {"date": e["time"].date(), "code": code}))
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
    if blue:
        return Finding("crashes", "problem", "bsod", {"n": len(blue), "days": EVENT_DAYS}, items, ["reliability"])
    if resets:
        return Finding("crashes", "warning", "resets", {"n": len(resets), "days": EVENT_DAYS}, items, ["reliability"])
    return Finding("crashes", "ok", "crashes_ok", {"days": EVENT_DAYS})


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
    return Finding("battery", severity, "battery", {"percent": health})


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
    items = []
    if state["uac_off"]:
        items.append(("item_uac_off", {}))
    if state["mitigations_off"]:
        items.append(("item_mitigations_off", {}))
    if not items:
        return Finding("security_settings", "ok", "security_ok")
    return Finding("security_settings", "warning", "security_off", {"n": len(items)}, items,
                   ["uac"] if state["uac_off"] else [])


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
    if not items:
        return Finding("secure_boot", "ok", "secure_ok")
    # Riot Vanguard refuses to start on Windows 11 without them; others such as Battlefield's and Call of Duty's
    # anti-cheats need them too
    severity = "warning" if state["anti_cheat"] else "info"
    return Finding("secure_boot", severity, "secure_off", {"n": len(items)}, items)


def check_windows_update(facts):
    settings = facts.get("update_settings")
    # The newest monthly update; the service's own date only if the servicing store cannot be read
    last = facts.get("windows_updated") or facts.get("last_update")
    if settings and settings["disabled"]:
        return Finding("windows_update", "problem", "wu_disabled", actions=["update"])
    if settings and settings["policy_off"]:
        return Finding("windows_update", "warning", "wu_policy", actions=["update"])
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
