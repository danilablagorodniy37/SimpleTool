"""The PC's specifications for a problem report: processor, graphics, memory, model and Windows.

Read from the registry and one Windows call, quickly and without administrator rights. Nothing here leaves the
PC by itself: the lines go into the email the user sends (and sees) from "Report a problem".
"""
import ctypes
import platform
import winreg

CPU_KEY = r"HARDWARE\DESCRIPTION\System\CentralProcessor\0"
BIOS_KEY = r"HARDWARE\DESCRIPTION\System\BIOS"
WINDOWS_KEY = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion"
# The device class of display adapters: one numbered subkey per installed adapter
DISPLAY_CLASS = r"SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}"


def _value(path, name):
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path, 0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as key:
            data = winreg.QueryValueEx(key, name)[0]
    except OSError:
        return None
    return " ".join(str(data).split()) or None  # processor names come padded with spaces


def processor():
    return _value(CPU_KEY, "ProcessorNameString")


def graphics():
    """Each display adapter with its driver version; the same adapter is listed once."""
    found = []
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, DISPLAY_CLASS, 0,
                            winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as key:
            count = winreg.QueryInfoKey(key)[0]
            names = [winreg.EnumKey(key, i) for i in range(count)]
    except OSError:
        return found
    for name in names:
        if not name.isdigit():
            continue  # "Properties" and other non-device subkeys
        adapter = _value(rf"{DISPLAY_CLASS}\{name}", "DriverDesc")
        if not adapter:
            continue
        driver = _value(rf"{DISPLAY_CLASS}\{name}", "DriverVersion")
        line = f"{adapter} (driver {driver})" if driver else adapter
        if line not in found:
            found.append(line)
    return found


class _MemoryStatus(ctypes.Structure):
    _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong)] + \
               [(name, ctypes.c_ulonglong) for name in ("ullTotalPhys", "ullAvailPhys", "ullTotalPageFile",
                                                        "ullAvailPageFile", "ullTotalVirtual", "ullAvailVirtual",
                                                        "ullAvailExtendedVirtual")]


def memory():
    """Installed memory in GB as Windows reports it, rounded to a tenth."""
    status = _MemoryStatus()
    status.dwLength = ctypes.sizeof(status)
    try:
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return None
    except (AttributeError, OSError):
        return None
    return round(status.ullTotalPhys / 1024 ** 3, 1)


# EditionID as people know the editions
EDITIONS = {"Professional": "Pro", "Core": "Home", "CoreSingleLanguage": "Home Single Language",
            "ProfessionalWorkstation": "Pro for Workstations", "ProfessionalEducation": "Pro Education",
            "IoTEnterprise": "IoT Enterprise"}


def windows():
    """"Windows 11 Pro 24H2, build 26100.6584". The registry still calls Windows 11 "Windows 10", so the build
    number decides."""
    build = _value(WINDOWS_KEY, "CurrentBuild")
    update = _value(WINDOWS_KEY, "UBR")
    edition = _value(WINDOWS_KEY, "EditionID")
    edition = EDITIONS.get(edition, edition)
    release = _value(WINDOWS_KEY, "DisplayVersion") or _value(WINDOWS_KEY, "ReleaseId")
    if not build:
        return f"Windows {platform.version()}"
    name = "Windows 11" if build.isdigit() and int(build) >= 22000 else "Windows 10"
    parts = [name, edition, release]
    text = " ".join(part for part in parts if part)
    return f"{text}, build {build}" + (f".{update}" if update else "")


def model():
    maker = _value(BIOS_KEY, "SystemManufacturer")
    product = _value(BIOS_KEY, "SystemProductName")
    text = " ".join(part for part in (maker, product) if part and part.lower() != "to be filled by o.e.m.")
    return text or None


def summary(app_line):
    """The lines for the report: app_line first (SimpleTool's version and state), then the PC."""
    lines = [app_line, f"Windows: {windows()} ({platform.machine()})"]
    lines.append(f"Processor: {processor() or 'unknown'}")
    adapters = graphics()
    lines += [f"Graphics: {adapter}" for adapter in adapters] or ["Graphics: unknown"]
    total = memory()
    lines.append(f"Memory: {total} GB" if total else "Memory: unknown")
    pc = model()
    if pc:
        lines.append(f"PC: {pc}")
    return lines
