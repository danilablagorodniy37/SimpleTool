"""Tweak engine: registry, services, scheduled tasks, shortcuts, backups and system snapshots."""
import ctypes
import datetime
import json
import os
import platform
import subprocess
import winreg
from ctypes import wintypes

CREATE_NO_WINDOW = 0x08000000
RUN_TIMEOUT = 300  # seconds: a console program that hangs must not keep SimpleTool busy forever
HIVES = {"HKLM": winreg.HKEY_LOCAL_MACHINE, "HKCU": winreg.HKEY_CURRENT_USER}
WOW64 = winreg.KEY_WOW64_64KEY

# Marker for "no value" in default values
ABSENT = object()


def is_admin():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except (AttributeError, OSError):
        return False


def other_account():
    """(the account SimpleTool runs as, the account signed in to Windows) when they differ, otherwise None.

    A standard user who elevates with an administrator's password starts SimpleTool as that administrator:
    HKCU, %LOCALAPPDATA% and the desktop then belong to the administrator, not to the person at the computer.
    """
    try:
        size = ctypes.c_ulong(0)
        secur32 = ctypes.windll.secur32
        secur32.GetUserNameExW(2, None, ctypes.byref(size))  # NameSamCompatible: DOMAIN\name
        name = ctypes.create_unicode_buffer(size.value + 1)
        if not secur32.GetUserNameExW(2, name, ctypes.byref(size)):
            return None
        wtsapi32 = ctypes.windll.wtsapi32
        wtsapi32.WTSQuerySessionInformationW.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int,
                                                         ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_ulong)]
        wtsapi32.WTSFreeMemory.argtypes = [ctypes.c_void_p]
        buffer, length = ctypes.c_void_p(), ctypes.c_ulong()
        # WTS_CURRENT_SESSION, WTSUserName: who is signed in to the session this process runs in
        if not wtsapi32.WTSQuerySessionInformationW(None, 0xFFFFFFFF, 5, ctypes.byref(buffer), ctypes.byref(length)):
            return None
        try:
            signed_in = ctypes.wstring_at(buffer.value)
        finally:
            wtsapi32.WTSFreeMemory(buffer)
    except (AttributeError, OSError):
        return None
    running = name.value.rpartition("\\")[2]
    # Only the names are compared: domain names are spelled differently by the two calls for some account types
    if not signed_in or not running or signed_in.lower() == running.lower():
        return None
    return running, signed_in


def data_dir():
    """Folder for settings and backups: %LOCALAPPDATA%\\SimpleTool."""
    path = os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"), "SimpleTool")
    os.makedirs(path, exist_ok=True)
    return path


def clean_env():
    """Environment for child programs with the default Windows PowerShell 5.1 module paths.

    If SimpleTool is started from PowerShell 7 or the system has its module paths set, Windows PowerShell
    loads incompatible PowerShell 7 modules and loses built-in cmdlets (Get-FileHash,
    Checkpoint-Computer). SimpleTool uses built-in modules only, so the paths are set explicitly.
    """
    env = dict(os.environ)
    env["PSModulePath"] = os.pathsep.join([
        os.path.expandvars(r"%ProgramFiles%\WindowsPowerShell\Modules"),
        os.path.expandvars(r"%SystemRoot%\System32\WindowsPowerShell\v1.0\Modules"),
    ])
    return env


def run(args, timeout=RUN_TIMEOUT):
    """Runs a console program without a window. On failure raises RuntimeError with its output."""
    try:
        result = subprocess.run(args, capture_output=True, encoding="oem", errors="replace",
                                creationflags=CREATE_NO_WINDOW, env=clean_env(), timeout=timeout)
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"{os.path.basename(args[0])} did not finish in {timeout} s") from None
    if result.returncode != 0:
        output = (result.stderr or result.stdout).strip()
        raise RuntimeError(output or f"{args[0]}: exit code {result.returncode}")
    return result.stdout


def powershell(script, timeout=RUN_TIMEOUT):
    return run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script], timeout)


# --- Services ---

SERVICE_CHANGE_CONFIG = 0x0002
SERVICE_NO_CHANGE = 0xFFFFFFFF


def set_start_type(name, start):
    """Changes a service's startup type through the service manager. Returns False if Windows refuses.

    The service manager reads the Start value from the registry only at boot. A value written straight to the
    registry is not seen until then, so a service started by a trigger (dmwappushservice) could start again
    while SimpleTool already shows it as disabled. The service manager applies the change at once and writes
    the same Start value itself. Only the startup type changes: "delayed start" is a separate setting.
    """
    try:
        advapi = ctypes.WinDLL("advapi32", use_last_error=True)
        advapi.OpenSCManagerW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD]
        advapi.OpenSCManagerW.restype = wintypes.HANDLE
        advapi.OpenServiceW.argtypes = [wintypes.HANDLE, wintypes.LPCWSTR, wintypes.DWORD]
        advapi.OpenServiceW.restype = wintypes.HANDLE
        advapi.ChangeServiceConfigW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD,
                                                wintypes.LPCWSTR, wintypes.LPCWSTR, ctypes.c_void_p,
                                                wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.LPCWSTR,
                                                wintypes.LPCWSTR]
        advapi.ChangeServiceConfigW.restype = wintypes.BOOL
        advapi.CloseServiceHandle.argtypes = [wintypes.HANDLE]
    except (AttributeError, OSError):
        return False
    scm = advapi.OpenSCManagerW(None, None, 0x0001)  # SC_MANAGER_CONNECT
    if not scm:
        return False
    try:
        service = advapi.OpenServiceW(scm, name, SERVICE_CHANGE_CONFIG)
        if not service:
            return False  # no such service, or Windows protects its configuration
        try:
            return bool(advapi.ChangeServiceConfigW(service, SERVICE_NO_CHANGE, start, SERVICE_NO_CHANGE,
                                                    None, None, None, None, None, None, None))
        finally:
            advapi.CloseServiceHandle(service)
    finally:
        advapi.CloseServiceHandle(scm)


# --- Registry ---

def _split(path):
    hive, _, sub = path.partition("\\")
    return HIVES[hive], sub


def read_value(path, name):
    """Returns (data, type) or None if the value does not exist."""
    hive, sub = _split(path)
    try:
        with winreg.OpenKey(hive, sub, 0, winreg.KEY_READ | WOW64) as key:
            return winreg.QueryValueEx(key, name)
    except FileNotFoundError:
        return None


def key_exists(path):
    hive, sub = _split(path)
    try:
        winreg.OpenKey(hive, sub, 0, winreg.KEY_READ | WOW64).Close()
        return True
    except FileNotFoundError:
        return False
    except PermissionError:
        return True  # the key exists, but only administrators can read it


def create_key(path):
    """Creates a key together with missing parents and returns the list of created keys."""
    hive_name, _, sub = path.partition("\\")
    parts = sub.split("\\")
    created = []
    for i in range(1, len(parts) + 1):
        current = hive_name + "\\" + "\\".join(parts[:i])
        if not key_exists(current):
            hive, current_sub = _split(current)
            winreg.CreateKeyEx(hive, current_sub, 0, winreg.KEY_WRITE | WOW64).Close()
            created.append(current)
    return created


def write_value(path, name, data, kind):
    hive, sub = _split(path)
    with winreg.CreateKeyEx(hive, sub, 0, winreg.KEY_SET_VALUE | WOW64) as key:
        winreg.SetValueEx(key, name, 0, kind, data)


def delete_value(path, name):
    hive, sub = _split(path)
    try:
        with winreg.OpenKey(hive, sub, 0, winreg.KEY_SET_VALUE | WOW64) as key:
            winreg.DeleteValue(key, name)
    except FileNotFoundError:
        pass


def is_empty_key(path):
    hive, sub = _split(path)
    try:
        with winreg.OpenKey(hive, sub, 0, winreg.KEY_READ | WOW64) as key:
            subkeys, values, _ = winreg.QueryInfoKey(key)
            return subkeys == 0 and values == 0
    except OSError:
        return False


def delete_key(path):
    hive, sub = _split(path)
    try:
        winreg.DeleteKeyEx(hive, sub, WOW64)
    except FileNotFoundError:
        pass


def delete_tree(path):
    hive, sub = _split(path)
    try:
        with winreg.OpenKey(hive, sub, 0, winreg.KEY_READ | WOW64) as key:
            children = [winreg.EnumKey(key, i) for i in range(winreg.QueryInfoKey(key)[0])]
    except FileNotFoundError:
        return
    for child in children:
        delete_tree(path + "\\" + child)
    delete_key(path)


def prune_empty_parents(path):
    """Deletes empty parent keys, but not above ...\\Classes."""
    if "\\classes\\" not in path.lower():
        return
    parent = path.rpartition("\\")[0]
    while parent.rpartition("\\")[2].lower() != "classes" and is_empty_key(parent):
        delete_key(parent)
        parent = parent.rpartition("\\")[0]


def _pack(found):
    """Registry data in a JSON-friendly form."""
    if found is None:
        return None
    data, kind = found
    if isinstance(data, bytes):
        data = {"hex": data.hex()}
    return [data, kind]


def _unpack(packed):
    data, kind = packed
    if isinstance(data, dict):
        data = bytes.fromhex(data["hex"])
    return data, kind


# --- Scheduled tasks, shortcuts ---

TASKS_SCRIPT = ("[Console]::OutputEncoding = New-Object Text.UTF8Encoding $false; "
                "Get-ScheduledTask | ForEach-Object { '{0}{1}|{2}' -f $_.TaskPath, $_.TaskName, [int]$_.State }")


def load_tasks():
    """Dict "lowercase task path -> whether it is disabled". None if the list could not be read."""
    try:
        result = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", TASKS_SCRIPT],
                                capture_output=True, encoding="utf-8", errors="replace",
                                creationflags=CREATE_NO_WINDOW, timeout=60, env=clean_env())
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    tasks = {}
    for line in result.stdout.splitlines():
        name, sep, state = line.lstrip("﻿").rpartition("|")
        if sep:
            tasks[name.strip("\\").lower()] = state.strip() == "1"  # 1 = Disabled
    return tasks


def desktop_dir():
    buf = ctypes.create_unicode_buffer(260)
    ctypes.windll.shell32.SHGetFolderPathW(None, 0x10, None, 0, buf)  # CSIDL_DESKTOPDIRECTORY
    return buf.value


def create_shortcut(lnk, target, args, icon):
    def quote(text):
        return "'" + text.replace("'", "''") + "'"
    # WScript.Shell mangles characters outside the system code page (Cyrillic on English Windows),
    # so the shortcut is saved under a Latin name and renamed from Python afterwards
    tmp = os.path.join(os.path.dirname(lnk), "SimpleTool-shortcut.tmp.lnk")
    powershell(f"$s = (New-Object -ComObject WScript.Shell).CreateShortcut({quote(tmp)}); "
               f"$s.TargetPath = {quote(target)}; $s.Arguments = {quote(args)}; "
               f"$s.IconLocation = {quote(icon)}; $s.Save()")
    os.replace(tmp, lnk)


def notify_shell():
    """Tells Explorer that file associations and context menus have changed."""
    try:
        ctypes.windll.shell32.SHChangeNotify(0x08000000, 0, None, None)  # SHCNE_ASSOCCHANGED
    except (AttributeError, OSError):
        pass


# --- Explorer ---
# Shell settings such as the Windows 11 context menu are read when Explorer starts, so it has to be restarted.

TH32CS_SNAPPROCESS = 0x2
PROCESS_TERMINATE = 0x0001
SYNCHRONIZE = 0x00100000
TOKEN_QUERY = 0x0008
TOKEN_DUPLICATE = 0x0002
CREATE_UNICODE_ENVIRONMENT = 0x400
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD), ("th32ProcessID", wintypes.DWORD),
                ("th32DefaultHeapID", ctypes.c_size_t), ("th32ModuleID", wintypes.DWORD),
                ("cntThreads", wintypes.DWORD), ("th32ParentProcessID", wintypes.DWORD),
                ("pcPriClassBase", wintypes.LONG), ("dwFlags", wintypes.DWORD), ("szExeFile", wintypes.WCHAR * 260)]


class STARTUPINFOW(ctypes.Structure):
    _fields_ = [("cb", wintypes.DWORD), ("lpReserved", wintypes.LPWSTR), ("lpDesktop", wintypes.LPWSTR),
                ("lpTitle", wintypes.LPWSTR), ("dwX", wintypes.DWORD), ("dwY", wintypes.DWORD),
                ("dwXSize", wintypes.DWORD), ("dwYSize", wintypes.DWORD), ("dwXCountChars", wintypes.DWORD),
                ("dwYCountChars", wintypes.DWORD), ("dwFillAttribute", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                ("wShowWindow", wintypes.WORD), ("cbReserved2", wintypes.WORD), ("lpReserved2", wintypes.LPBYTE),
                ("hStdInput", wintypes.HANDLE), ("hStdOutput", wintypes.HANDLE), ("hStdError", wintypes.HANDLE)]


class PROCESS_INFORMATION(ctypes.Structure):
    _fields_ = [("hProcess", wintypes.HANDLE), ("hThread", wintypes.HANDLE), ("dwProcessId", wintypes.DWORD),
                ("dwThreadId", wintypes.DWORD)]


def explorer_pids():
    """Process ids of explorer.exe in this session: this user's desktop, taskbar and folder windows."""
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel32.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
    kernel32.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    session, own = wintypes.DWORD(), wintypes.DWORD()
    kernel32.ProcessIdToSessionId(kernel32.GetCurrentProcessId(), ctypes.byref(own))
    snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snapshot in (None, INVALID_HANDLE_VALUE):
        raise ctypes.WinError(ctypes.get_last_error())
    pids = []
    try:
        entry = PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(entry)
        found = kernel32.Process32FirstW(snapshot, ctypes.byref(entry))
        while found:
            if (entry.szExeFile.lower() == "explorer.exe"
                    and kernel32.ProcessIdToSessionId(entry.th32ProcessID, ctypes.byref(session))
                    and session.value == own.value):
                pids.append(entry.th32ProcessID)
            found = kernel32.Process32NextW(snapshot, ctypes.byref(entry))
    finally:
        kernel32.CloseHandle(snapshot)
    return pids


def start_explorer():
    """Starts Explorer with the user's own environment from the registry, not SimpleTool's.

    A onefile exe carries PyInstaller variables and SimpleTool sets PowerShell paths; Explorer would pass them on to
    every program started from the taskbar. Started by an administrator, Explorer drops the elevation itself.
    """
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
    userenv = ctypes.WinDLL("userenv", use_last_error=True)
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CreateProcessW.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, ctypes.c_void_p, ctypes.c_void_p,
                                        wintypes.BOOL, wintypes.DWORD, ctypes.c_void_p, wintypes.LPCWSTR,
                                        ctypes.POINTER(STARTUPINFOW), ctypes.POINTER(PROCESS_INFORMATION)]
    advapi32.OpenProcessToken.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)]
    userenv.CreateEnvironmentBlock.argtypes = [ctypes.POINTER(ctypes.c_void_p), wintypes.HANDLE, wintypes.BOOL]
    userenv.DestroyEnvironmentBlock.argtypes = [ctypes.c_void_p]
    path = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "explorer.exe")
    token = wintypes.HANDLE()
    if not advapi32.OpenProcessToken(kernel32.GetCurrentProcess(), TOKEN_QUERY | TOKEN_DUPLICATE, ctypes.byref(token)):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        environment = ctypes.c_void_p()
        if not userenv.CreateEnvironmentBlock(ctypes.byref(environment), token, False):
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            info, process = STARTUPINFOW(), PROCESS_INFORMATION()
            info.cb = ctypes.sizeof(info)
            command = ctypes.create_unicode_buffer(f'"{path}"')
            if not kernel32.CreateProcessW(path, command, None, None, False, CREATE_UNICODE_ENVIRONMENT, environment,
                                           os.path.expanduser("~"), ctypes.byref(info), ctypes.byref(process)):
                raise ctypes.WinError(ctypes.get_last_error())
            kernel32.CloseHandle(process.hProcess)
            kernel32.CloseHandle(process.hThread)
        finally:
            userenv.DestroyEnvironmentBlock(environment)
    finally:
        kernel32.CloseHandle(token)


def restart_explorer():
    """Restarts this user's Explorer so that shell settings take effect; open folder windows close.

    Returns False without doing anything when SimpleTool runs as another account than the one signed in: the new
    Explorer would belong to that account. The user then signs out instead.
    """
    if other_account():
        return False
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
    kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    for pid in explorer_pids():
        handle = kernel32.OpenProcess(PROCESS_TERMINATE | SYNCHRONIZE, False, pid)
        if not handle:
            continue  # already gone
        try:
            kernel32.TerminateProcess(handle, 1)
            kernel32.WaitForSingleObject(handle, 5000)
        finally:
            kernel32.CloseHandle(handle)
    start_explorer()
    return True


# --- Tweak operations ---
# Every operation has: admin, id, available(ctx), applied(ctx) -> True/False/None (None = does not affect the status),
# snapshot(ctx) -> state before applying, apply(lang) -> list of created keys, restore(snapshot), reset().

class Unknown(Exception):
    """The state of an operation could not be read; reason is the key of the explanation in the UI."""

    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason

class Value:
    """A registry value. data can be a function of the language (menu item labels)."""

    def __init__(self, path, name, data, kind=winreg.REG_DWORD, default=ABSENT, check=True):
        self.path, self.name, self.data, self.kind = path, name, data, kind
        self.default, self.check = default, check
        self.admin = not path.startswith("HKCU")
        self.id = f"value:{path}|{name}"

    def __str__(self):
        return f"{self.path}\\{self.name or '(Default)'}"

    def available(self, ctx):
        return True

    def applied(self, ctx):
        if not self.check:
            return None
        found = read_value(self.path, self.name)
        return found is not None and found[0] == self.data

    def snapshot(self, ctx):
        return _pack(read_value(self.path, self.name))

    def apply(self, lang):
        created = create_key(self.path)
        data = self.data(lang) if callable(self.data) else self.data
        write_value(self.path, self.name, data, self.kind)
        return created

    def restore(self, snap):
        if snap is None:
            delete_value(self.path, self.name)
        else:
            write_value(self.path, self.name, *_unpack(snap))

    def reset(self):
        if self.default is ABSENT:
            delete_value(self.path, self.name)
        else:
            write_value(self.path, self.name, self.default, self.kind)


class OwnedKey:
    """A key that a tweak creates (a context menu item). It is deleted entirely on revert."""

    def __init__(self, path):
        self.path = path
        self.admin = not path.startswith("HKCU")
        self.id = f"key:{path}"

    def __str__(self):
        return self.path

    def available(self, ctx):
        return True

    def applied(self, ctx):
        return None

    def snapshot(self, ctx):
        return key_exists(self.path)

    def apply(self, lang):
        return create_key(self.path)

    def restore(self, existed):
        if existed:
            create_key(self.path)
        else:
            self.reset()

    def reset(self):
        delete_tree(self.path)
        prune_empty_parents(self.path)


class Service:
    """A Windows service: disable automatic start (Start = 4) and stop it."""

    def __init__(self, name, default_start):
        self.name, self.default_start = name, default_start
        self.path = rf"HKLM\SYSTEM\CurrentControlSet\Services\{name}"
        self.admin = True
        self.id = f"service:{name}"

    def __str__(self):
        return self.name

    def available(self, ctx):
        return key_exists(self.path)

    def applied(self, ctx):
        found = read_value(self.path, "Start")
        return found is not None and found[0] == 4

    def snapshot(self, ctx):
        found = read_value(self.path, "Start")
        return found[0] if found else None

    def set_start(self, start):
        # Some services refuse configuration changes even to administrators: for them only the registry
        # value can be changed, and it takes effect after a restart
        if not set_start_type(self.name, start):
            write_value(self.path, "Start", start, winreg.REG_DWORD)

    def apply(self, lang):
        self.set_start(4)
        try:
            run(["sc.exe", "stop", self.name])
        except RuntimeError:
            pass  # the service is already stopped
        return []

    def restore(self, start):
        if start is not None:
            self.set_start(start)

    def reset(self):
        self.set_start(self.default_start)


class Task:
    """A scheduled task: disable it."""

    def __init__(self, path):
        self.path = path
        self.admin = True
        self.id = f"task:{path.lower()}"

    def __str__(self):
        return self.path

    def available(self, ctx):
        return ctx.tasks is None or self.path.lower() in ctx.tasks

    def applied(self, ctx):
        if ctx.tasks is None:
            raise Unknown("tasks_unavailable")
        return ctx.tasks.get(self.path.lower())

    def snapshot(self, ctx):
        # True = the task was enabled. Without the task list the state is unknown: guessing "enabled" would make
        # revert and the original snapshot enable tasks that were disabled before
        if ctx.tasks is None:
            raise OSError("the state of scheduled tasks could not be read")
        return not ctx.tasks.get(self.path.lower(), False)

    def apply(self, lang):
        run(["schtasks.exe", "/change", "/tn", self.path, "/disable"])
        return []

    def restore(self, was_enabled):
        run(["schtasks.exe", "/change", "/tn", self.path, "/enable" if was_enabled else "/disable"])

    def reset(self):
        run(["schtasks.exe", "/change", "/tn", self.path, "/enable"])


class Shortcut:
    """A desktop shortcut. names is the shortcut name in each language."""

    def __init__(self, names, target, args, icon):
        self.names = names
        self.target, self.args, self.icon = (os.path.expandvars(x) for x in (target, args, icon))
        self.admin = False
        self.id = f"shortcut:{names['en']}"

    def __str__(self):
        return self.names["en"]

    def _paths(self):
        return [os.path.join(desktop_dir(), name + ".lnk") for name in self.names.values()]

    def available(self, ctx):
        return os.path.exists(self.target)

    def applied(self, ctx):
        return any(os.path.exists(path) for path in self._paths())

    def snapshot(self, ctx):
        return [path for path in self._paths() if os.path.exists(path)]

    def apply(self, lang):
        path = os.path.join(desktop_dir(), self.names[lang] + ".lnk")
        if not os.path.exists(path):  # a shortcut of the user's own with the same name is not overwritten
            create_shortcut(path, self.target, self.args, self.icon)
        return []

    def restore(self, existed):
        for path in self._paths():
            if path in existed:
                if not os.path.exists(path):
                    create_shortcut(path, self.target, self.args, self.icon)
            elif os.path.exists(path):
                os.remove(path)

    def reset(self):
        self.restore([])


class Tweak:
    def __init__(self, id, category, ops, requires=None, effect=None):
        """effect: what the change needs before it shows. "explorer": SimpleTool restarts Explorer after applying or
        reverting; "signout" and "restart": the user is told to sign out or restart the PC."""
        self.id, self.category, self.ops, self.requires, self.effect = id, category, ops, requires, effect
        self.admin = any(op.admin for op in ops)

    def available_ops(self, ctx):
        if self.requires and not self.requires():
            return []
        return [op for op in self.ops if _try(op.available, ctx, default=True)]


class Context:
    """Data shared by the checks of all tweaks: the state of scheduled tasks."""

    def __init__(self):
        self.tasks = load_tasks()


def _try(check, ctx, default=None):
    """A check that may lack read access (without administrator rights); then default."""
    try:
        return check(ctx)
    except OSError:
        return default


def check(tweak, ctx):
    """The state of a tweak and of each of its operations.

    Returns (status, rows): status is applied / partial / not_applied / unknown / unavailable,
    rows is a list of (operation, applied: True/False/None, reason: None / "missing" / a key from reasons).
    """
    if tweak.requires and not tweak.requires():
        return "unavailable", []
    rows = []
    for op in tweak.ops:
        if not _try(op.available, ctx, default=True):
            rows.append((op, None, "missing"))
            continue
        try:
            rows.append((op, op.applied(ctx), None))
        except Unknown as exc:
            rows.append((op, None, exc.reason))
        except PermissionError:
            rows.append((op, None, "access_denied"))
        except OSError:
            rows.append((op, None, "error"))
    present = [row for row in rows if row[2] != "missing"]
    if not present:
        return "unavailable", rows
    known = [state for _, state, _ in present if state is not None]
    unknown = any(reason for _, _, reason in present)
    if any(known) and not all(known):
        status = "partial"
    elif known and not any(known):
        status = "not_applied"  # at least one part is definitely not applied
    elif unknown or not known:
        status = "unknown"
    else:
        status = "applied"
    return status, rows


def status(tweak, ctx):
    return check(tweak, ctx)[0]


# --- Apply and revert with a backup ---

def backup_path():
    return os.path.join(data_dir(), "backup.json")


def write_json(path, data):
    """Writes the file whole or not at all: a crash or a power cut leaves either the old or the new version."""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def load_backup():
    try:
        with open(backup_path(), encoding="utf-8") as f:
            backup = json.load(f)
        if isinstance(backup, dict):
            return backup
    except FileNotFoundError:
        return {}
    except (OSError, ValueError):
        pass
    # A damaged backup is kept aside rather than overwritten by the next save: the originals in it may be recoverable
    try:
        os.replace(backup_path(), f"{backup_path()}.damaged-{datetime.datetime.now():%Y%m%d-%H%M%S}")
    except OSError:
        pass
    return {}


def save_backup(backup):
    write_json(backup_path(), backup)


def apply(tweak, lang, ctx):
    """Applies a tweak. Before an operation is changed for the first time, remembers its original state.

    Returns a list of errors.
    """
    errors = []
    backup = load_backup()
    entry = backup.setdefault(tweak.id, {"ops": {}, "created": []})
    ops = []
    for op in tweak.available_ops(ctx):
        if op.id not in entry["ops"]:
            try:
                entry["ops"][op.id] = op.snapshot(ctx)
            except OSError as exc:
                # An operation whose original state was not saved is not applied: it could not be reverted
                errors.append(f"{op}: {exc}")
                continue
        ops.append(op)
    if not entry["ops"]:
        del backup[tweak.id]
        return errors
    # The originals are on disk before anything changes: a failed write or a crash later cannot lose them
    save_backup(backup)
    for op in ops:
        try:
            entry["created"] += op.apply(lang)
        except (OSError, RuntimeError) as exc:
            errors.append(f"{op}: {exc}")
    save_backup(backup)
    return errors


def revert(tweak, ctx):
    """Restores the original state from the backup, or the Windows defaults without one."""
    errors = []
    backup = load_backup()
    entry = backup.pop(tweak.id, None)
    for op in reversed(tweak.available_ops(ctx)):
        try:
            if entry is None:
                op.reset()
            elif op.id in entry["ops"]:
                op.restore(entry["ops"][op.id])
            # An operation missing from the backup was never changed by SimpleTool: it is left alone
        except (OSError, RuntimeError) as exc:
            errors.append(f"{op}: {exc}")
    if entry is not None:
        # Keys created while applying are deleted if they are left empty (deepest first)
        for path in sorted(set(entry["created"]), key=lambda p: p.count("\\"), reverse=True):
            try:
                if is_empty_key(path):
                    delete_key(path)
            except OSError:
                pass
        if errors:
            backup[tweak.id] = entry
    save_backup(backup)
    return errors


def forget_backups(keep):
    """Deletes backups of tweaks not in keep: after a snapshot restore they are out of date."""
    backup = load_backup()
    for tweak_id in [i for i in backup if i not in keep]:
        del backup[tweak_id]
    save_backup(backup)


# --- System snapshots: the state of everything SimpleTool changes at a given moment ---

AUTO_SNAPSHOTS_KEPT = 20  # the original snapshot and manual snapshots are never deleted


def snapshots_dir():
    path = os.path.join(data_dir(), "snapshots")
    os.makedirs(path, exist_ok=True)
    return path


def take_snapshot(tweaks, ctx, kind, statuses, app_version):
    """Saves the current state of every operation of every tweak. Returns the path to the snapshot file."""
    now = datetime.datetime.now()
    data = {"format": 1, "app": app_version, "windows": platform.version(),
            "created": now.isoformat(timespec="seconds"), "kind": kind, "tweaks": {}, "keys": {}}
    for tweak in tweaks:
        ops = {}
        for op in tweak.available_ops(ctx):
            try:
                ops[op.id] = op.snapshot(ctx)
            except OSError:
                continue  # without administrator rights some values cannot be read
            if isinstance(op, (Value, OwnedKey)):
                # Which registry keys existed: keys created later are deleted on restore
                parts = op.path.split("\\")
                for i in range(2, len(parts) + 1):
                    path = "\\".join(parts[:i])
                    if path not in data["keys"]:
                        data["keys"][path] = key_exists(path)
        data["tweaks"][tweak.id] = {"status": statuses.get(tweak.id), "ops": ops}
    base = os.path.join(snapshots_dir(), f"{now:%Y-%m-%d_%H-%M-%S}_{kind}")
    path, n = base + ".json", 1
    while os.path.exists(path):
        n += 1
        path = f"{base}_{n}.json"
    write_json(path, data)
    prune_snapshots()
    return path


def list_snapshots():
    """Snapshots from newest to oldest: a list of (path, data)."""
    items = []
    for name in os.listdir(snapshots_dir()):
        if name.endswith(".json"):
            path = os.path.join(snapshots_dir(), name)
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
            except (OSError, ValueError):
                continue
            if isinstance(data, dict) and isinstance(data.get("tweaks"), dict):  # a damaged file is skipped
                items.append((path, data))
    items.sort(key=lambda item: str(item[1].get("created") or ""), reverse=True)
    return items


def prune_snapshots():
    automatic = [path for path, data in list_snapshots() if data.get("kind") not in ("initial", "manual")]
    for path in automatic[AUTO_SNAPSHOTS_KEPT:]:
        try:
            os.remove(path)
        except OSError:
            pass


def restore_snapshot(tweaks, data, ctx):
    """Returns every operation saved in the snapshot to its state at that moment. Returns errors."""
    errors = []
    for tweak in tweaks:
        entry = data.get("tweaks", {}).get(tweak.id)
        if not entry:
            continue
        for op in reversed(tweak.available_ops(ctx)):
            if op.id in entry["ops"]:
                try:
                    op.restore(entry["ops"][op.id])
                except (OSError, RuntimeError) as exc:
                    errors.append(f"{op}: {exc}")
    created = [path for path, existed in data.get("keys", {}).items() if not existed]
    for path in sorted(created, key=lambda p: p.count("\\"), reverse=True):
        try:
            if is_empty_key(path):
                delete_key(path)
        except OSError:
            pass
    return errors


# The volumes System Protection is on for, one "\\?\Volume{...}\:(C%3A)" line each
PROTECTED_VOLUMES = (r"HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\SPP\Clients",
                     "{09F7EDC5-294E-4180-AF6A-FB0E6A0E9513}")
RESTORE_POINT_AGE = datetime.timedelta(hours=24)  # Windows itself allows one restore point a day by default
RESTORE_POINT_TIMEOUT = 900  # creating a restore point on a slow disk can take several minutes

LAST_RESTORE_POINT_SCRIPT = (
    "$point = @(Get-ComputerRestorePoint -ErrorAction Stop) | Sort-Object SequenceNumber | Select-Object -Last 1; "
    "if ($point) { [Management.ManagementDateTimeConverter]::ToDateTime($point.CreationTime).ToUniversalTime()"
    ".ToString('yyyy-MM-ddTHH:mm:ss') } else { 'NONE' }")

RESTORE_POINT_SCRIPT = (
    "$before = @(Get-ComputerRestorePoint -ErrorAction SilentlyContinue).Count; "
    "Checkpoint-Computer -Description 'SimpleTool' -RestorePointType MODIFY_SETTINGS "
    "-WarningVariable warn -WarningAction SilentlyContinue -ErrorAction Stop; "
    "$after = @(Get-ComputerRestorePoint -ErrorAction SilentlyContinue).Count; "
    "if ($after -gt $before) { 'CREATED' } else { 'NOT CREATED: ' + ($warn -join ' ') }")

# Without System Protection on the Windows drive, Windows creates no restore points at all
ENABLE_PROTECTION_SCRIPT = "Enable-ComputerRestore -Drive ($env:SystemDrive + '\\') -ErrorAction Stop; "


def system_protection_on():
    """Whether System Protection is on for the Windows drive; None if that cannot be read."""
    try:
        found = read_value(*PROTECTED_VOLUMES)
    except OSError:
        return None
    volumes = found[0] if found and isinstance(found[0], list) else []
    drive = (os.environ.get("SystemDrive") or "C:").rstrip("\\").upper().replace(":", "%3A")
    return any(f"({drive})" in str(volume).upper() for volume in volumes)


def last_restore_point():
    """When the newest Windows restore point was created (UTC), or None if there is none.

    Needs administrator rights. Raises RuntimeError if Windows cannot list restore points.
    """
    output = powershell(LAST_RESTORE_POINT_SCRIPT).strip()
    last = output.splitlines()[-1].strip() if output else ""
    if last == "NONE":
        return None
    try:
        return datetime.datetime.strptime(last, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=datetime.timezone.utc)
    except ValueError:
        raise RuntimeError(output or "Get-ComputerRestorePoint returned nothing") from None


def recent_restore_point(now=None):
    """The newest restore point if it is less than a day old, otherwise None (raises like last_restore_point)."""
    created = last_restore_point()
    now = now or datetime.datetime.now(datetime.timezone.utc)
    return created if created and now - created < RESTORE_POINT_AGE else None


def create_restore_point():
    """A Windows restore point (the whole registry and system files).

    If System Protection is off for the Windows drive it is turned on first: the dialog that asks for the
    restore point says so. Returns (success, Windows message, whether System Protection was turned on).
    """
    enable = system_protection_on() is False
    try:
        output = powershell((ENABLE_PROTECTION_SCRIPT if enable else "") + RESTORE_POINT_SCRIPT,
                            RESTORE_POINT_TIMEOUT).strip()
    except RuntimeError as exc:
        return False, str(exc), enable
    last = output.splitlines()[-1] if output else ""
    if last == "CREATED":
        return True, "", enable
    return False, last.replace("NOT CREATED:", "").strip(), enable
