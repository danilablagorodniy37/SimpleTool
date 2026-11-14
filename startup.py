"""Startup: the programs that start when you sign in to Windows, turned on and off the way Task Manager does it.

The sources are the ones Task Manager's Startup apps page lists: the Run keys of the account and of the PC (64-bit
and 32-bit programs), the Startup folders of the account and of every account, and the startup tasks of Microsoft
Store apps. A program is turned off without touching its own entry: Windows keeps the choice next to it
(StartupApproved for the Run keys and the Startup folders, the State of a Store app's task). Turning it on again
brings back exactly what was there, and the program's own settings and updates still find their entry.

Only an entry whose program is gone can be removed: a Run value is saved to startup-removed.json first, a shortcut
goes to the Recycle Bin.
"""
import datetime
import json
import os
import shutil
import struct
import time
import winreg

import diagnostics
import engine
import storeapps
import uninstaller

APPROVED = r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved"
# (scope, Run key, its StartupApproved key): scope HKLM is every account, changed with administrator rights only
RUN_KEYS = [("HKCU", r"HKCU\Software\Microsoft\Windows\CurrentVersion\Run", rf"HKCU\{APPROVED}\Run"),
            ("HKLM", r"HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Run", rf"HKLM\{APPROVED}\Run"),
            ("HKLM", r"HKLM\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Run", rf"HKLM\{APPROVED}\Run32")]
FOLDERS = [("HKCU", r"%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup", rf"HKCU\{APPROVED}\StartupFolder"),
           ("HKLM", r"%ProgramData%\Microsoft\Windows\Start Menu\Programs\StartUp", rf"HKLM\{APPROVED}\StartupFolder")]
APP_MODEL = r"HKCU\Software\Classes\Local Settings\Software\Microsoft\Windows\CurrentVersion\AppModel"
APP_TASKS = APP_MODEL + r"\SystemAppData"
APP_PACKAGES = APP_MODEL + r"\Repository\Packages"
# StartupTaskState of a Store app's startup task (Windows.ApplicationModel.StartupTaskState)
TASK_DISABLED, TASK_DISABLED_BY_USER, TASK_ENABLED, TASK_DISABLED_BY_POLICY, TASK_ENABLED_BY_POLICY = range(5)
# StartupApproved data: the first byte odd means off; Task Manager writes 03 + 3 zero bytes + the time it was turned
# off (FILETIME) to turn a program off, and 02 + 11 zero bytes to turn it on
APPROVED_ON = b"\x02" + b"\0" * 11
HOSTS = {"rundll32.exe"}  # programs that run a DLL named in the command: the DLL is what the entry starts


class Entry:
    """One program that starts with Windows."""

    def __init__(self, key, name, command, path, source, scope, enabled, approved=None, location="", policy=False):
        self.key = key            # unique: "run:<Run key>:<value>", "folder:<shortcut path>", "app:<package>\\<task>"
        self.name = name          # the value name, the shortcut name or the app's name
        self.command = command    # what starts: the command line, the shortcut's target, or the app's package
        self.path = path          # the program's file, "" when unknown (a Store app)
        self.source = source      # "run", "folder" or "app"
        self.scope = scope        # "HKCU": this account, "HKLM": every account (needs administrator rights)
        self.enabled = enabled
        self.approved = approved  # (StartupApproved key, value name) for Run keys and Startup folders
        self.location = location  # the Run key, the shortcut file or the app's task key
        self.policy = policy      # turned on or off by a policy: cannot be changed here
        self.title = name         # the program's own description, when its file has one
        self.publisher = ""
        self.impact = None        # {"cpu" ms, "disk" bytes, "starts"} as Windows measured the last starts
        self.logo = None          # the logo file of a Store app

    def __repr__(self):
        return f"Entry({self.name!r}, {self.key!r}, enabled={self.enabled})"

    @property
    def needs_admin(self):
        return self.scope == "HKLM"

    @property
    def missing(self):
        """Whether the file the entry starts is gone: then it starts nothing and can be removed."""
        path = self.path
        return bool(path) and os.path.isabs(path) and uninstaller._local(path) and not os.path.exists(path)

    @property
    def changeable(self):
        return not self.policy


def _values(path):
    hive, sub = engine._split(path)
    try:
        with winreg.OpenKey(hive, sub, 0, winreg.KEY_READ | engine.WOW64) as key:
            return [winreg.EnumValue(key, i)[:2] for i in range(winreg.QueryInfoKey(key)[1])]
    except OSError:
        return []


def _subkeys(path):
    hive, sub = engine._split(path)
    try:
        with winreg.OpenKey(hive, sub, 0, winreg.KEY_READ | engine.WOW64) as key:
            return [winreg.EnumKey(key, i) for i in range(winreg.QueryInfoKey(key)[0])]
    except OSError:
        return []


def approved_on(data):
    """Whether StartupApproved data leaves a program on: no data, or a first byte that is even."""
    return not (isinstance(data, bytes) and data and data[0] & 1)


def program_file(command):
    """The file a command line starts, found on the PATH when the command names it without a folder:
    '"C:\\x\\app.exe" --hidden' -> 'C:\\x\\app.exe'; for rundll32 the DLL it runs."""
    path = uninstaller.command_program(command)
    if os.path.basename(path).lower() in HOSTS:
        rest = os.path.expandvars(command or "")
        rest = rest[rest.lower().find("rundll32") + len("rundll32"):]
        rest = rest[4:] if rest.lower().startswith(".exe") else rest
        rest = rest.strip().lstrip('"')
        dll = rest.split(",", 1)[0].strip().strip('"')
        if dll:
            path = dll
    if path and not os.path.isabs(path):
        found = shutil.which(path) or shutil.which(path, path=os.path.join(
            os.environ.get("SystemRoot", r"C:\Windows"), "System32"))
        path = found or path
    return os.path.normpath(path) if path else ""


def _run_entries():
    found = []
    for scope, run, approval in RUN_KEYS:
        states = {name.lower(): data for name, data in _values(approval)}
        for name, data in _values(run):
            if not name or not isinstance(data, str) or not data.strip():
                continue
            found.append(Entry(f"run:{run}:{name}", name, data, program_file(data), "run", scope,
                               approved_on(states.get(name.lower())), (approval, name), run))
    return found


def _folder_entries():
    found = []
    for scope, folder, approval in FOLDERS:
        folder = os.path.expandvars(folder)
        states = {name.lower(): data for name, data in _values(approval)}
        try:
            files = sorted(os.listdir(folder))
        except OSError:
            continue
        for file in files:
            path = os.path.join(folder, file)
            if file.lower() == "desktop.ini" or not os.path.isfile(path):
                continue
            target = uninstaller._shortcut_target(path) if file.lower().endswith(".lnk") else path
            found.append(Entry(f"folder:{path}", os.path.splitext(file)[0], target or path,
                               os.path.normpath(target) if target else "", "folder", scope,
                               approved_on(states.get(file.lower())), (approval, file), path))
    return found


def app_info(package):
    """(the name a Store app shows, its logo file or None) from its package full name; the package name when the
    name cannot be read."""
    path = rf"{APP_PACKAGES}\{package}"
    name = package.split("_")[0]
    title = storeapps.resolve(package, name, _read(path, "DisplayName") or "")
    folder, logo = _read(path, "PackageRootFolder"), None
    if isinstance(folder, str) and folder:
        manifest = storeapps.read_manifest(folder)
        if manifest and manifest[0].get("Logo"):
            logo = storeapps.logo_file(folder, manifest[0]["Logo"])
    return title or name.rpartition(".")[2] or package, logo


def _read(path, name):
    """A registry value, or None."""
    try:
        found = engine.read_value(path, name)
    except OSError:
        return None
    return found[0] if found else None


def _app_entries():
    found = []
    for family in _subkeys(APP_TASKS):
        package = _read(rf"{APP_TASKS}\{family}\Schemas", "PackageFullName")
        for task in _subkeys(rf"{APP_TASKS}\{family}"):
            path = rf"{APP_TASKS}\{family}\{task}"
            state = _read(path, "State")
            if not isinstance(state, int) or not package:
                continue  # not a startup task, or an app no longer installed
            title, logo = app_info(package)
            entry = Entry(f"app:{family}\\{task}", title, package, "", "app", "HKCU",
                          state in (TASK_ENABLED, TASK_ENABLED_BY_POLICY), location=path,
                          policy=state in (TASK_DISABLED_BY_POLICY, TASK_ENABLED_BY_POLICY))
            entry.logo = logo
            found.append(entry)
    # Two tasks of one app get the task's name too
    names = [entry.name for entry in found]
    for entry in found:
        if names.count(entry.name) > 1:
            entry.name = f"{entry.name} ({entry.location.rpartition(chr(92))[2]})"
            entry.title = entry.name
    return found


def entries(impact=None):
    """Every program that starts with Windows, with its description, publisher and the cost Windows measured
    (impact: diagnostics.startup_impact(), read here when not given; it needs administrator rights)."""
    found = _run_entries() + _folder_entries() + _app_entries()
    if impact is None:
        try:
            impact = diagnostics.startup_impact() or []
        except OSError:
            impact = []
    costs = {os.path.normcase(item["path"]): item for item in impact if item.get("path")}
    for entry in found:
        if entry.path and os.path.isfile(entry.path):
            title = diagnostics.file_description(entry.path)
            # An updater or launcher that starts the program (Discord's "Update" by GitHub) says nothing about it:
            # the name the program gave its entry does
            if title and not uninstaller.NOT_THE_PROGRAM.search(title):
                entry.title = title
                entry.publisher = diagnostics.version_string(entry.path, "CompanyName") or ""
        cost = costs.get(os.path.normcase(entry.path)) if entry.path else None
        if cost:
            entry.impact = {"cpu": cost["cpu"], "disk": cost["disk"], "starts": cost.get("starts", 0)}
    return found


def _filetime(now=None):
    """Now as a FILETIME: 100 ns since 1601."""
    now = time.time() if now is None else now
    return int((now + 11644473600) * 10_000_000)


def set_enabled(entry, on):
    """Turns a program on or off at sign-in, as Task Manager does. Raises PermissionError without the rights."""
    if entry.policy:
        raise PermissionError(entry.name)
    if entry.source == "app":
        engine.write_value(entry.location, "State", TASK_ENABLED if on else TASK_DISABLED_BY_USER, winreg.REG_DWORD)
        if not on:
            engine.write_value(entry.location, "LastDisabledTime", int(time.time()) & 0xFFFFFFFF, winreg.REG_DWORD)
    else:
        key, name = entry.approved
        data = APPROVED_ON if on else b"\x03\0\0\0" + struct.pack("<Q", _filetime())
        engine.write_value(key, name, data, winreg.REG_BINARY)
    entry.enabled = on


def removed_file():
    return os.path.join(engine.data_dir(), "startup-removed.json")


def remove(entry):
    """Removes an entry whose program is gone. A Run value is saved to startup-removed.json first, a shortcut goes
    to the Recycle Bin; Task Manager's on/off mark for it is removed too."""
    if entry.source == "app" or not entry.missing:
        raise ValueError(entry.name)
    if entry.source == "run":
        found = engine.read_value(entry.location, entry.name)
        if found:
            saved = _read_removed()
            saved.append({"key": entry.location, "name": entry.name, "data": found[0], "type": found[1],
                          "removed": datetime.datetime.now().isoformat(timespec="seconds")})
            engine.write_json(removed_file(), saved)
            engine.delete_value(entry.location, entry.name)
    else:
        uninstaller.to_recycle_bin(entry.location)
    if entry.approved:
        engine.delete_value(*entry.approved)


def _read_removed():
    try:
        with open(removed_file(), encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (OSError, ValueError):
        return []
