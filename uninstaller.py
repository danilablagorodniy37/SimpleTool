"""Programs: the installed programs with their own icons, their uninstallers, and what they leave behind.

A program is removed the way full uninstallers such as Reg Organizer do it: a Windows restore point first, then
the program's own uninstaller (it knows what it installed), and only after it a search for what is left: the
program's folders, registry keys, shortcuts and startup entries. Leftovers are matched by the program's own names
and folders, never by loose parts of words, and system places, shared places and the folders of other installed
programs are never offered. Registry keys are saved to a .reg file before they are deleted and files go to the
Recycle Bin, so everything removed can be brought back.
"""
import ctypes
import datetime
import json
import os
import re
import struct
import subprocess
import time
import winreg
from ctypes import wintypes

import engine
import programs
import raster

UNINSTALL_KEYS = [r"HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
                  r"HKLM\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
                  r"HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall"]
UPDATE_TYPES = ("update", "hotfix", "security update", "update rollup", "service pack")
MSI_COMMAND = re.compile(r"msiexec(?:\.exe)?\W.*?/[ix]\s*(\{[0-9a-f-]{36}\})", re.IGNORECASE)
PRODUCT_CODE = re.compile(r"^\{[0-9a-f-]{36}\}$", re.IGNORECASE)
# Executables in a program's folder that are not the program itself, for its icon
NOT_THE_PROGRAM = re.compile(r"unins|setup|install|updat|crash|report|helper|service|elevat|launcher_?stub",
                             re.IGNORECASE)
# Words of a name that say nothing about which program it is
VERSION_WORDS = re.compile(r"\b(x64|x86|amd64|arm64|win64|win32|64-bit|32-bit|64 bit|32 bit|version|"
                           r"v?\d+(\.\d+)+(-\d+)?)\b", re.IGNORECASE)
GENERIC_NAMES = {"common", "commonfiles", "shared", "update", "updater", "updates", "data", "program", "programs",
                 "microsoft", "windows", "system", "system32", "temp", "tmp", "cache", "logs", "log", "user", "users",
                 "app", "apps", "application", "applications", "tools", "tool", "games", "game", "software", "setup",
                 "install", "installer", "bin", "lib", "config", "settings", "local", "roaming", "default", "public",
                 "documents", "downloads", "desktop", "packages", "drivers", "driver", "plugins", "addons", "runtime",
                 # Makers whose folder holds several products, and Steam, whose folder holds the installed games
                 "intel", "amd", "nvidia", "realtek", "google", "mozilla", "adobe", "apple", "steam", "epicgames"}
MIN_NAME = 4  # shorter names ("App", "Hub") match too much

# Registry keys under Software that belong to Windows or to everyone: never offered, nor their parents
SHARED_KEYS = {"microsoft", "classes", "policies", "wow6432node", "clients", "registeredapplications", "windows",
               "odbc", "intel", "amd", "nvidia", "realtek", "google", "mozilla", "adobe", "apple", "valve", "khronos",
               "oem", "partner", "chromium", "jre", "javasoft", "python", "wix"}
RUN_KEYS = [r"HKCU\Software\Microsoft\Windows\CurrentVersion\Run",
            r"HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Run",
            r"HKLM\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Run"]
APP_PATHS = [r"HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths",
             r"HKCU\Software\Microsoft\Windows\CurrentVersion\App Paths"]
JOB_POLL = 0.5  # seconds between looks at whether the uninstaller and the programs it started are still running


# --- Names ---

def clean_name(name):
    """A name without what changes between versions: "7-Zip 24.08 (x64)" -> "7-zip"."""
    name = re.sub(r"[®™©]", "", name or "")
    name = re.sub(r"\([^)]*\)|\[[^\]]*\]", " ", name)
    name = VERSION_WORDS.sub(" ", name)
    return " ".join(name.lower().replace("_", " ").split()).strip(" -.,")


def compact(name):
    """The letters, digits and pluses of a cleaned name: "Notepad++" -> "notepad++", "Proton Mail" -> "protonmail"."""
    return re.sub(r"[^\w+]|_", "", clean_name(name))


def _usable(token):
    return len(token) >= MIN_NAME and token not in GENERIC_NAMES


# --- Programs ---

class Program:
    """One entry of Windows' list of installed programs."""

    def __init__(self, key, name, publisher="", version="", size=0, installed=None, location="", icon=None,
                 uninstall="", msi=None, user=False, removable=True):
        self.key = key              # its registry key, 64-bit view: HKLM\SOFTWARE\WOW6432Node\... for 32-bit ones
        self.name = name
        self.publisher = publisher
        self.version = version
        self.size = size            # bytes, 0 when the program does not say
        self.installed = installed  # a date or None
        self.location = location    # its install folder, "" when unknown
        self.icon = icon            # (file, index) or None
        self.uninstall = uninstall  # the command line of its uninstaller, "" when it has none
        self.msi = msi              # the product code of a Windows Installer product
        self.user = user            # installed for this account only: no administrator rights needed
        self.removable = removable  # False when Windows marks it as not to be removed (NoRemove), as Edge

    def __repr__(self):
        return f"Program({self.name!r}, {self.key!r})"

    @property
    def uninstaller_missing(self):
        """Whether the uninstaller the entry names is gone: then only its leftovers can be removed."""
        if not self.removable or self.msi or not self.uninstall:
            return False
        path = command_program(self.uninstall)
        return bool(path) and os.path.isabs(path) and _local(path) and not os.path.exists(path)


def _local(path):
    """Whether a path is on a local disk. A share of a computer that is off can keep a check of a file waiting for
    a minute: such paths count as unknown, never as missing."""
    drive = os.path.splitdrive(path or "")[0]
    if len(drive) != 2:  # \\server\share, or no drive at all
        return False
    return ctypes.windll.kernel32.GetDriveTypeW(drive + "\\") not in (1, 4)  # no such drive, network drive


def command_program(command):
    """The program a command line starts: '"C:\\x\\unins000.exe" /SILENT' -> 'C:\\x\\unins000.exe'."""
    command = os.path.expandvars((command or "").strip())
    if command.startswith('"'):
        return command[1:].split('"', 1)[0]
    match = re.match(r"(.+?\.(?:exe|com|bat|cmd))(?:\s|$)", command, re.IGNORECASE)
    if match:
        return match.group(1)
    return command.split()[0] if command.split() else ""


def _value(key, name):
    try:
        return winreg.QueryValueEx(key, name)[0]
    except OSError:
        return None


def _filetime_date(value):
    return (datetime.datetime(1601, 1, 1) + datetime.timedelta(microseconds=value // 10)).date() if value else None


def _install_date(text, key):
    if isinstance(text, str) and re.fullmatch(r"\d{8}", text.strip()):
        try:
            return datetime.datetime.strptime(text.strip(), "%Y%m%d").date()
        except ValueError:
            pass
    try:
        return _filetime_date(winreg.QueryInfoKey(key)[2])  # when the entry was last written
    except OSError:
        return None


def parse_icon(value):
    """(file, index) of a DisplayIcon value: '"C:\\a\\b.exe",0' -> ("C:\\a\\b.exe", 0); None when unusable."""
    if not isinstance(value, str) or not value.strip():
        return None
    text, index = value.strip(), 0
    match = re.match(r"^(.*?),\s*(-?\d+)$", text)
    if match:
        text, index = match.group(1), int(match.group(2))
    path = os.path.expandvars(text.strip().strip('"'))
    return (path, index) if path else None


def _msi_icon(code):
    """The icon Windows Installer keeps for a product it installed (its ARPPRODUCTICON), or None."""
    get = ctypes.windll.msi.MsiGetProductInfoW
    get.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
    get.restype = wintypes.UINT
    size = wintypes.DWORD(1024)
    buffer = ctypes.create_unicode_buffer(size.value)
    if get(code, "ProductIcon", buffer, ctypes.byref(size)) != 0:
        return None
    return parse_icon(buffer.value)


def _icon_source(icon, location, uninstall, name, msi=None):
    """The file to take a program's icon from: its DisplayIcon, the icon Windows Installer keeps for it, else the
    program's own exe in its folder."""
    for found in (parse_icon(icon), _msi_icon(msi) if msi else None):
        if found and _local(found[0]) and os.path.isfile(found[0]):
            return found
    if location and _local(location) and os.path.isdir(location):
        try:
            exes = [entry.path for entry in os.scandir(location) if entry.is_file() and
                    entry.name.lower().endswith(".exe") and not NOT_THE_PROGRAM.search(entry.name)]
        except OSError:
            exes = []
        target = compact(name)
        exes.sort(key=lambda path: (compact(os.path.splitext(os.path.basename(path))[0]) not in target, path))
        if exes:
            return exes[0], 0
    program = command_program(uninstall)
    if program and _local(program) and os.path.isfile(program) and "msiexec" not in program.lower():
        return program, 0
    return None


def installed_programs():
    """The programs of Windows' list of installed programs, without components, updates and duplicates,
    alphabetically. Reading their folders for icons can wake sleeping drives: call it from a background thread."""
    found, seen = [], set()
    for path in UNINSTALL_KEYS:
        hive, sub = engine._split(path)
        try:
            root = winreg.OpenKey(hive, sub, 0, winreg.KEY_READ | engine.WOW64)
        except OSError:
            continue
        with root:
            count = winreg.QueryInfoKey(root)[0]
            for i in range(count):
                try:
                    name = winreg.EnumKey(root, i)
                    key = winreg.OpenKey(root, name)
                except OSError:
                    continue
                with key:
                    program = _program(path + "\\" + name, name, key, path.startswith("HKCU"))
                if program and (program.name.lower(), program.version) not in seen:
                    seen.add((program.name.lower(), program.version))
                    found.append(program)
    return sorted(found, key=lambda p: p.name.lower())


def _program(path, subkey, key, user):
    title = _value(key, "DisplayName")
    if not isinstance(title, str) or not title.strip() or _value(key, "SystemComponent") == 1:
        return None
    if _value(key, "ParentKeyName") or str(_value(key, "ReleaseType") or "").lower() in UPDATE_TYPES:
        return None  # updates of another product
    uninstall = _value(key, "UninstallString")
    uninstall = uninstall.strip() if isinstance(uninstall, str) else ""
    msi = None
    if _value(key, "WindowsInstaller") == 1 and PRODUCT_CODE.match(subkey):
        msi = subkey.upper()
    else:
        match = MSI_COMMAND.search(uninstall)
        msi = match.group(1).upper() if match else None
    removable = _value(key, "NoRemove") != 1 and bool(uninstall or msi)
    size = _value(key, "EstimatedSize")
    location = _value(key, "InstallLocation")
    location = os.path.expandvars(location.strip().strip('"')).rstrip("\\") if isinstance(location, str) else ""
    publisher, version = _value(key, "Publisher"), _value(key, "DisplayVersion")
    return Program(path, title.strip(), publisher.strip() if isinstance(publisher, str) else "",
                   version.strip() if isinstance(version, str) else "",
                   size * 1024 if isinstance(size, int) and size > 0 else 0,
                   _install_date(_value(key, "InstallDate"), key), location,
                   _icon_source(_value(key, "DisplayIcon"), location, uninstall, title, msi), uninstall, msi, user,
                   removable)


def still_installed(program):
    """Whether the program is still there after its uninstaller ran: its entry and its uninstaller remain (the
    user cancelled), or Windows Installer still knows the product."""
    if not engine.key_exists(program.key):
        return False
    if program.msi:
        query = ctypes.windll.msi.MsiQueryProductStateW
        query.argtypes, query.restype = [wintypes.LPCWSTR], ctypes.c_int
        return query(program.msi) == 5  # INSTALLSTATE_DEFAULT: installed
    return not program.uninstaller_missing


# --- Icons ---

class _IconInfo(ctypes.Structure):
    _fields_ = [("fIcon", wintypes.BOOL), ("xHotspot", wintypes.DWORD), ("yHotspot", wintypes.DWORD),
                ("hbmMask", wintypes.HBITMAP), ("hbmColor", wintypes.HBITMAP)]


class _BitmapInfoHeader(ctypes.Structure):
    _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG), ("biHeight", wintypes.LONG),
                ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
                ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD), ("biClrImportant", wintypes.DWORD)]


def _bits(bitmap, size):
    """The pixels of a bitmap as top-down BGRA rows."""
    header = _BitmapInfoHeader(ctypes.sizeof(_BitmapInfoHeader), size, -size, 1, 32, 0, 0, 0, 0, 0, 0)
    buffer = ctypes.create_string_buffer(size * size * 4)
    gdi32, user32 = ctypes.windll.gdi32, ctypes.windll.user32
    dc = user32.GetDC(None)
    try:
        lines = gdi32.GetDIBits(dc, bitmap, 0, size, buffer, ctypes.byref(header), 0)
    finally:
        user32.ReleaseDC(None, dc)
    return buffer.raw if lines == size else None


def icon_png(path, index=0, size=32):
    """A program's icon as a PNG of size x size pixels with its transparency, or None."""
    user32 = ctypes.windll.user32
    user32.PrivateExtractIconsW.argtypes = [wintypes.LPCWSTR, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                            ctypes.POINTER(wintypes.HICON), ctypes.c_void_p, wintypes.UINT,
                                            wintypes.UINT]
    user32.GetIconInfo.argtypes = [wintypes.HICON, ctypes.POINTER(_IconInfo)]
    user32.DestroyIcon.argtypes = [wintypes.HICON]
    ctypes.windll.gdi32.GetDIBits.argtypes = [wintypes.HDC, wintypes.HBITMAP, wintypes.UINT, wintypes.UINT,
                                              ctypes.c_void_p, ctypes.c_void_p, wintypes.UINT]
    ctypes.windll.gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
    icon = wintypes.HICON()
    if user32.PrivateExtractIconsW(path, index, size, size, ctypes.byref(icon), None, 1, 0) != 1 or not icon:
        return None
    info = _IconInfo()
    try:
        if not user32.GetIconInfo(icon, ctypes.byref(info)) or not info.hbmColor:
            return None
        color = _bits(info.hbmColor, size)
        if color is None:
            return None
        pixels = bytearray(color)
        if not any(pixels[3::4]):
            # An old icon without an alpha channel: its mask says which pixels are see-through (white)
            mask = _bits(info.hbmMask, size)
            if mask is None:
                return None
            pixels[3::4] = bytes(0 if mask[i] else 255 for i in range(0, len(mask), 4))
        rgba = bytearray(pixels)
        rgba[0::4], rgba[2::4] = pixels[2::4], pixels[0::4]  # BGRA -> RGBA
        return raster.png(size, size, bytes(rgba))
    finally:
        for bitmap in (info.hbmMask, info.hbmColor):
            if bitmap:
                ctypes.windll.gdi32.DeleteObject(bitmap)
        user32.DestroyIcon(icon)


# --- Running the uninstaller ---

class _JobAccounting(ctypes.Structure):  # JOBOBJECT_BASIC_ACCOUNTING_INFORMATION
    _fields_ = [("TotalUserTime", ctypes.c_longlong), ("TotalKernelTime", ctypes.c_longlong),
                ("ThisPeriodTotalUserTime", ctypes.c_longlong), ("ThisPeriodTotalKernelTime", ctypes.c_longlong),
                ("TotalPageFaultCount", wintypes.DWORD), ("TotalProcesses", wintypes.DWORD),
                ("ActiveProcesses", wintypes.DWORD), ("TotalTerminatedProcesses", wintypes.DWORD)]


def uninstall_command(program):
    """The command line that starts the program's uninstaller. Windows Installer products are removed with
    msiexec /x: their entries often say /i, which opens the "change or repair" screen instead. Entries written as
    REG_EXPAND_SZ keep names like %ProgramFiles%, which only Windows' shell would fill in."""
    if program.msi:
        msiexec = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "msiexec.exe")
        return f'"{msiexec}" /x {program.msi}'
    return os.path.expandvars(program.uninstall)


def run_uninstaller(program):
    """Runs the program's uninstaller and waits until it and every program it started have finished: Inno Setup and
    NSIS uninstallers copy themselves to the temporary folder, start the copy and quit at once. They run in a job
    object, which counts them. Returns the exit code of the uninstaller itself."""
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateJobObjectW.restype = wintypes.HANDLE
    kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel32.QueryInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD,
                                                   ctypes.c_void_p]
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    job = kernel32.CreateJobObjectW(None, None)
    # Started suspended, so that nothing it starts can slip out before it is in the job
    try:
        process = subprocess.Popen(uninstall_command(program), creationflags=0x4)  # CREATE_SUSPENDED
    except OSError as exc:
        if job:
            kernel32.CloseHandle(job)
        if getattr(exc, "winerror", None) == 740:  # it asks for administrator rights: Windows' prompt, then wait
            return _run_elevated(uninstall_command(program))
        raise
    try:
        if job:
            kernel32.AssignProcessToJobObject(job, int(process._handle))
        ctypes.windll.ntdll.NtResumeProcess(wintypes.HANDLE(int(process._handle)))
        process.wait()
        while job:
            info = _JobAccounting()
            if not kernel32.QueryInformationJobObject(job, 1, ctypes.byref(info), ctypes.sizeof(info), None) \
                    or info.ActiveProcesses == 0:
                break
            time.sleep(JOB_POLL)
        return process.returncode
    finally:
        if job:
            kernel32.CloseHandle(job)


class _ShellExecuteInfo(ctypes.Structure):  # SHELLEXECUTEINFOW
    _fields_ = [("cbSize", wintypes.DWORD), ("fMask", wintypes.ULONG), ("hwnd", wintypes.HWND),
                ("lpVerb", wintypes.LPCWSTR), ("lpFile", wintypes.LPCWSTR), ("lpParameters", wintypes.LPCWSTR),
                ("lpDirectory", wintypes.LPCWSTR), ("nShow", ctypes.c_int), ("hInstApp", wintypes.HINSTANCE),
                ("lpIDList", ctypes.c_void_p), ("lpClass", wintypes.LPCWSTR), ("hkeyClass", wintypes.HKEY),
                ("dwHotKey", wintypes.DWORD), ("hIconOrMonitor", wintypes.HANDLE), ("hProcess", wintypes.HANDLE)]


def _run_elevated(command):
    """Starts an uninstaller that needs administrator rights through Windows' consent prompt and waits for it."""
    program = command_program(command)
    stripped = command.strip()
    rest = stripped[len(program) + 2:] if stripped.startswith('"') else stripped[len(program):]
    info = _ShellExecuteInfo(ctypes.sizeof(_ShellExecuteInfo), 0x40 | 0x100, None, "runas", program,
                             rest.strip() or None, None, 1)  # SEE_MASK_NOCLOSEPROCESS | SEE_MASK_NOASYNC
    if not ctypes.windll.shell32.ShellExecuteExW(ctypes.byref(info)) or not info.hProcess:
        raise OSError("the uninstaller did not start")
    kernel32 = ctypes.windll.kernel32
    kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    try:
        kernel32.WaitForSingleObject(info.hProcess, 0xFFFFFFFF)
        code = wintypes.DWORD()
        kernel32.GetExitCodeProcess(info.hProcess, ctypes.byref(code))
        return code.value
    finally:
        kernel32.CloseHandle(info.hProcess)


# --- Leftovers ---

def _norm(path):
    return os.path.normcase(os.path.normpath(path)).rstrip("\\") if path else ""


def _known_folders():
    names = ("SystemDrive", "SystemRoot", "ProgramFiles", "ProgramFiles(x86)", "ProgramW6432", "ProgramData",
             "CommonProgramFiles", "CommonProgramFiles(x86)", "CommonProgramW6432", "USERPROFILE", "APPDATA",
             "LOCALAPPDATA", "PUBLIC", "TEMP", "TMP", "ALLUSERSPROFILE")
    folders = {os.environ.get(name, "") for name in names}
    profile, local = os.environ.get("USERPROFILE", ""), os.environ.get("LOCALAPPDATA", "")
    appdata, data = os.environ.get("APPDATA", ""), os.environ.get("ProgramData", "")
    folders |= {os.path.join(profile, sub) for sub in ("AppData", r"AppData\LocalLow", "Desktop", "Documents",
                                                       "Downloads", "Music", "Pictures", "Videos", "Saved Games")}
    folders |= {os.path.join(local, sub) for sub in ("Programs", "Packages", "Microsoft", "Temp", "VirtualStore")}
    folders |= {os.path.join(root, r"Microsoft\Windows\Start Menu", sub) for root in (appdata, data)
                for sub in ("", "Programs", r"Programs\Startup")}
    folders |= {os.path.join(appdata, "Microsoft"), os.path.join(data, "Microsoft"),
                os.path.join(os.environ.get("PUBLIC", ""), "Desktop")}
    return {_norm(f) for f in folders if f}


def protected_folder(path, other_locations=()):
    """Whether a folder must never be offered for removal: a drive, a folder of Windows or of every user, anything
    inside Windows, a folder that holds one of them, or the folder of another installed program (or its parent)."""
    path = _norm(path)
    if not path or len(path) <= 3 or "\\" not in path:
        return True
    windows = _norm(os.environ.get("SystemRoot", r"C:\Windows"))
    if path == windows or path.startswith(windows + "\\"):
        return True
    if any(path == known or known.startswith(path + "\\") for known in _known_folders()):
        return True
    if not _usable(compact(os.path.basename(path))):
        return True
    return any(path == other or other.startswith(path + "\\") for other in map(_norm, other_locations) if other)


def protected_key(path):
    """Whether a registry key must never be offered: Software itself and the keys of Windows and of everyone."""
    parts = [p.lower() for p in path.split("\\")]
    if len(parts) < 3 or parts[1] != "software":
        return True
    rest = parts[2:]
    if rest[0] == "wow6432node":
        rest = rest[1:]
    if not rest or rest[0] in SHARED_KEYS:
        return True
    return not _usable(compact(rest[-1]))


def _subfolders(folder):
    try:
        return [entry.path for entry in os.scandir(folder) if entry.is_dir(follow_symlinks=False)]
    except OSError:
        return []


def _subkey_names(path):
    hive, sub = engine._split(path)
    try:
        with winreg.OpenKey(hive, sub, 0, winreg.KEY_READ | engine.WOW64) as key:
            return [winreg.EnumKey(key, i) for i in range(winreg.QueryInfoKey(key)[0])]
    except OSError:
        return []


def _key_counts(path):
    hive, sub = engine._split(path)
    try:
        with winreg.OpenKey(hive, sub, 0, winreg.KEY_READ | engine.WOW64) as key:
            subkeys, values, _ = winreg.QueryInfoKey(key)
            return subkeys, values
    except OSError:
        return None


def folder_size(path, limit=20000):
    """Bytes in a folder, counting at most limit files: a rough size for the list of leftovers."""
    total, seen, stack = 0, 0, [path]
    while stack and seen < limit:
        try:
            entries = list(os.scandir(stack.pop()))
        except OSError:
            continue
        for entry in entries:
            seen += 1
            try:
                if entry.is_dir(follow_symlinks=False):
                    stack.append(entry.path)
                else:
                    total += entry.stat(follow_symlinks=False).st_size
            except OSError:
                continue
    return total


def program_names(program, others=()):
    """The compact names leftovers are matched by: the program's name, and its install folder's name. A name that
    another installed program shares, or that begins another one's, is left out: "python" belongs to every
    version of Python, and "protonmail" also begins "protonmailbridge", whose data is in a "protonmail" folder."""
    names = {compact(program.name)}
    if program.location:
        names.add(compact(os.path.basename(program.location)))
    taken = set()
    for other in others:
        if other.key != program.key:
            taken.add(compact(other.name))
            if other.location:
                taken.add(compact(os.path.basename(other.location)))
    return {name for name in names if _usable(name) and not any(t.startswith(name) for t in taken if t)}


def find_leftovers(program, others=()):
    """What the program left after its uninstaller ran: [{"kind": "folder"|"file"|"key"|"value", "path", "name",
    "size"}]. others are the programs still installed: their folders are never offered."""
    names, publisher = program_names(program, others), compact(program.publisher.split(",")[0])
    other_locations = [p.location for p in others if p.location and p.key != program.key]
    found, seen = [], set()

    def add(kind, path, name="", size=0):
        marker = (kind, _norm(path) if kind in ("folder", "file") else path.lower(), name)
        if marker not in seen:
            seen.add(marker)
            found.append({"kind": kind, "path": path, "name": name, "size": size})

    # The install folder, and the folders the entry points into, when they are still there
    folders = {program.location}
    if program.icon:
        folders.add(os.path.dirname(program.icon[0]))
    uninstaller = command_program(program.uninstall)
    if uninstaller and os.path.isabs(uninstaller) and "msiexec" not in uninstaller.lower():
        folders.add(os.path.dirname(uninstaller))
    # The folder must carry the program's own name (or its publisher's): an entry that names a folder of a whole
    # disk or a library of games is not trusted
    own = {name for name in (compact(program.name), publisher) if _usable(name)}
    for folder in folders:
        if folder and _local(folder) and os.path.isdir(folder) and compact(os.path.basename(folder)) in own \
                and not protected_folder(folder, other_locations):
            add("folder", folder, size=folder_size(folder))
    # Folders named after the program where programs keep their files and settings, directly or in a folder of
    # their publisher
    bases = {os.environ.get(name, "") for name in ("ProgramFiles", "ProgramFiles(x86)", "ProgramData", "APPDATA",
                                                   "LOCALAPPDATA")}
    bases |= {os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs"),
              os.path.join(os.environ.get("USERPROFILE", ""), r"AppData\LocalLow")}
    for base in filter(None, bases):
        for folder in _subfolders(base):
            name = compact(os.path.basename(folder))
            if name in names and not protected_folder(folder, other_locations):
                add("folder", folder, size=folder_size(folder))
            elif _usable(publisher) and name == publisher:
                for inner in _subfolders(folder):
                    if compact(os.path.basename(inner)) in names and not protected_folder(inner, other_locations):
                        add("folder", inner, size=folder_size(inner))
    # Start menu folders and shortcuts, and shortcuts on the desktops that lead to nowhere now
    for root in (os.path.join(os.environ.get(v, ""), r"Microsoft\Windows\Start Menu\Programs")
                 for v in ("APPDATA", "ProgramData")):
        for folder in _subfolders(root):
            name = compact(os.path.basename(folder))
            # A publisher's folder may hold the shortcuts of its other programs: only when every one is dead
            if (name in names or _usable(publisher) and name == publisher and
                    all(_dead_shortcut(lnk) for lnk in _shortcuts(folder))) and \
                    not protected_folder(folder, other_locations):
                add("folder", folder, size=folder_size(folder))
        for lnk in _shortcuts(root):
            if compact(os.path.splitext(os.path.basename(lnk))[0]) in names and _dead_shortcut(lnk):
                add("file", lnk)
    for desktop in (os.path.join(os.environ.get("USERPROFILE", ""), "Desktop"),
                    os.path.join(os.environ.get("PUBLIC", ""), "Desktop")):
        for lnk in _shortcuts(desktop, recursive=False):
            if compact(os.path.splitext(os.path.basename(lnk))[0]) in names and _dead_shortcut(lnk):
                add("file", lnk)
    # The entry itself, when the uninstaller left it behind
    if engine.key_exists(program.key):
        add("key", program.key)
    # Registry keys named after the program, directly under Software or under its publisher's key
    for root in (r"HKCU\Software", r"HKLM\SOFTWARE", r"HKLM\SOFTWARE\WOW6432Node"):
        children = {compact(child): child for child in _subkey_names(root)}
        for name in names:
            if name in children and not protected_key(f"{root}\\{children[name]}"):
                add("key", f"{root}\\{children[name]}")
        if _usable(publisher) and publisher in children and publisher not in SHARED_KEYS:
            vendor = f"{root}\\{children[publisher]}"
            products = [child for child in _subkey_names(vendor) if compact(child) in names]
            counts = _key_counts(vendor)
            if products and counts and counts == (len(products), 0) and not protected_key(vendor):
                add("key", vendor)  # nothing else of the publisher there: the whole key
            else:
                for child in products:
                    if not protected_key(f"{vendor}\\{child}"):
                        add("key", f"{vendor}\\{child}")
    # Startup entries and App Paths that start the program's files, which are gone
    removed = [f["path"] for f in found if f["kind"] == "folder"] + [p for p in folders if p]
    for key in RUN_KEYS:
        for name, data in _values(key):
            target = command_program(data) if isinstance(data, str) else ""
            if target and (_inside(target, removed) or compact(name) in names) and _local(target) \
                    and not os.path.exists(target):
                add("value", key, name)
    for root in APP_PATHS:
        for child in _subkey_names(root):
            target = engine.read_value(f"{root}\\{child}", "")
            target = command_program(target[0]) if target and isinstance(target[0], str) else ""
            if target and _inside(target, removed) and _local(target) and not os.path.exists(target):
                add("key", f"{root}\\{child}")
    # A folder inside another one found is removed with it
    folders_found = [_norm(f["path"]) for f in found if f["kind"] == "folder"]
    return [f for f in found if not (f["kind"] in ("folder", "file") and
                                     any(_norm(f["path"]).startswith(other + "\\") for other in folders_found))]


def needs_admin(leftovers):
    """Whether removing these leftovers takes administrator rights: anything outside this account's part of the
    registry and its profile folder."""
    profile = os.environ.get("USERPROFILE", "")
    for item in leftovers:
        if item["kind"] in ("key", "value"):
            if not item["path"].upper().startswith("HKCU\\"):
                return True
        elif not (profile and _inside(item["path"], [profile])):
            return True
    return False


def _values(path):
    hive, sub = engine._split(path)
    try:
        with winreg.OpenKey(hive, sub, 0, winreg.KEY_READ | engine.WOW64) as key:
            return [winreg.EnumValue(key, i)[:2] for i in range(winreg.QueryInfoKey(key)[1])]
    except OSError:
        return []


def _inside(path, folders):
    path = _norm(path)
    return any(folder and (path == _norm(folder) or path.startswith(_norm(folder) + "\\")) for folder in folders)


def _shortcuts(folder, recursive=True):
    found = []
    try:
        for entry in os.scandir(folder):
            if entry.is_file() and entry.name.lower().endswith(".lnk"):
                found.append(entry.path)
            elif recursive and entry.is_dir(follow_symlinks=False):
                found += _shortcuts(entry.path)
    except OSError:
        pass
    return found


def _shortcut_target(path):
    """Where a shortcut leads, "" when it cannot be read."""
    try:
        with open(path, "rb") as f:
            return programs.shortcut_target(f.read())[0] or ""
    except (OSError, ValueError, UnicodeDecodeError, struct.error):
        return ""


def _dead_shortcut(path):
    """Whether a shortcut points to a file that no longer exists."""
    target = _shortcut_target(path)
    return bool(target) and os.path.isabs(target) and _local(target) and not os.path.exists(target)


# --- Programs removed without SimpleTool ---

def _known_file():
    return os.path.join(engine.data_dir(), "programs.json")


def _read_known():
    try:
        with open(_known_file(), encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _record(program):
    return {"name": program.name, "publisher": program.publisher, "version": program.version,
            "location": program.location, "icon": list(program.icon) if program.icon else None,
            "uninstall": program.uninstall, "user": program.user}


def _from_record(key, record):
    icon = record.get("icon")
    return Program(key, str(record.get("name") or ""), str(record.get("publisher") or ""),
                   str(record.get("version") or ""), location=str(record.get("location") or ""),
                   icon=(str(icon[0]), int(icon[1])) if isinstance(icon, list) and len(icon) == 2 else None,
                   uninstall=str(record.get("uninstall") or ""), user=bool(record.get("user")))


def removed_elsewhere(current):
    """The programs that were in the list when SimpleTool read it before and are gone now: removed through
    Windows' settings or their own uninstaller, without SimpleTool. Remembers the current list for the next time.
    Returns [(Program, the date it was found gone)], until forget() is called for it or it is installed again."""
    data = _read_known()
    known, gone = data.get("installed"), data.get("gone") or {}
    keys = {program.key for program in current}
    if isinstance(known, dict):  # nothing to compare with on the first read
        today = datetime.date.today().isoformat()
        for key, record in known.items():
            if key not in keys and key not in gone and isinstance(record, dict) and record.get("name"):
                gone[key] = dict(record, gone=today)
    gone = {key: record for key, record in gone.items() if key not in keys and isinstance(record, dict)}
    engine.write_json(_known_file(), {"installed": {p.key: _record(p) for p in current}, "gone": gone})
    found = []
    for key, record in gone.items():
        try:
            day = datetime.date.fromisoformat(record.get("gone", ""))
        except (TypeError, ValueError):
            day = None
        found.append((_from_record(key, record), day))
    return found


def forget(key):
    """Stops offering the leftovers of a program: they were removed or the user keeps them. A program SimpleTool
    uninstalled itself is forgotten too, so that it is not taken for one removed without SimpleTool."""
    data = _read_known()
    changed = False
    for part in ("installed", "gone"):
        if isinstance(data.get(part), dict) and key in data[part]:
            del data[part][key]
            changed = True
    if changed:
        engine.write_json(_known_file(), data)


# --- Removing leftovers ---

class _FileOp(ctypes.Structure):  # SHFILEOPSTRUCTW
    _fields_ = [("hwnd", wintypes.HWND), ("wFunc", wintypes.UINT), ("pFrom", wintypes.LPCWSTR),
                ("pTo", wintypes.LPCWSTR), ("fFlags", ctypes.c_uint16), ("fAnyOperationsAborted", wintypes.BOOL),
                ("hNameMappings", ctypes.c_void_p), ("lpszProgressTitle", wintypes.LPCWSTR)]


FO_DELETE = 3
FOF_ALLOWUNDO, FOF_NOCONFIRMATION, FOF_WANTNUKEWARNING = 0x40, 0x10, 0x4000


def to_recycle_bin(path):
    """Moves a file or folder to the Recycle Bin. Windows asks first if it is too big for the bin."""
    operation = _FileOp(None, FO_DELETE, os.path.abspath(path) + "\0", None,
                        FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_WANTNUKEWARNING, False, None, None)
    result = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(operation))
    if result or operation.fAnyOperationsAborted:
        raise OSError(f"{path}: {'cancelled' if operation.fAnyOperationsAborted else f'error {result}'}")


def backup_dir(program):
    stamp = datetime.datetime.now().strftime("%Y-%m-%d %H-%M-%S")
    name = re.sub(r'[<>:"/\\|?*]', "", program.name)[:60].strip() or "program"
    path = os.path.join(engine.data_dir(), "uninstalled", f"{stamp} {name}")
    os.makedirs(path, exist_ok=True)
    return path


def remove_leftovers(program, leftovers):
    """Removes the chosen leftovers: registry keys are exported to .reg files first and values written down, files
    and folders go to the Recycle Bin. Returns (the backup folder, [errors])."""
    folder, errors, saved = backup_dir(program), [], {"program": program.name, "removed": []}
    for number, item in enumerate(leftovers, 1):
        try:
            if item["kind"] == "key":
                engine.run(["reg.exe", "export", item["path"], os.path.join(folder, f"{number:02}.reg"), "/y"])
                engine.delete_tree(item["path"])
            elif item["kind"] == "value":
                found = engine.read_value(item["path"], item["name"])
                if found:
                    saved.setdefault("values", []).append({"key": item["path"], "name": item["name"],
                                                           "data": found[0], "type": found[1]})
                engine.delete_value(item["path"], item["name"])
            else:
                to_recycle_bin(item["path"])
            saved["removed"].append(item)
        except (OSError, RuntimeError) as exc:
            errors.append(f"{item['path']}: {exc}")
    engine.write_json(os.path.join(folder, "removed.json"), saved)
    return folder, errors
