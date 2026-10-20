"""Tweak engine: registry, services, scheduled tasks, shortcuts, backups and system snapshots."""
import ctypes
import datetime
import json
import os
import platform
import subprocess
import winreg

CREATE_NO_WINDOW = 0x08000000
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


def run(args):
    """Runs a console program without a window. On failure raises RuntimeError with its output."""
    result = subprocess.run(args, capture_output=True, encoding="oem", errors="replace",
                            creationflags=CREATE_NO_WINDOW, env=clean_env())
    if result.returncode != 0:
        output = (result.stderr or result.stdout).strip()
        raise RuntimeError(output or f"{args[0]}: exit code {result.returncode}")
    return result.stdout


def powershell(script):
    return run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script])


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

    def apply(self, lang):
        write_value(self.path, "Start", 4, winreg.REG_DWORD)
        try:
            run(["sc.exe", "stop", self.name])
        except RuntimeError:
            pass  # the service is already stopped
        return []

    def restore(self, start):
        if start is not None:
            write_value(self.path, "Start", start, winreg.REG_DWORD)

    def reset(self):
        write_value(self.path, "Start", self.default_start, winreg.REG_DWORD)


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
    def __init__(self, id, category, ops, requires=None):
        self.id, self.category, self.ops, self.requires = id, category, ops, requires
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


RESTORE_POINT_SCRIPT = (
    "$before = @(Get-ComputerRestorePoint -ErrorAction SilentlyContinue).Count; "
    "Checkpoint-Computer -Description 'SimpleTool' -RestorePointType MODIFY_SETTINGS "
    "-WarningVariable warn -WarningAction SilentlyContinue -ErrorAction Stop; "
    "$after = @(Get-ComputerRestorePoint -ErrorAction SilentlyContinue).Count; "
    "if ($after -gt $before) { 'CREATED' } else { 'NOT CREATED: ' + ($warn -join ' ') }")


def create_restore_point():
    """A Windows restore point (the whole registry and system files). Returns (success, Windows message)."""
    try:
        output = powershell(RESTORE_POINT_SCRIPT).strip()
    except RuntimeError as exc:
        return False, str(exc)
    last = output.splitlines()[-1] if output else ""
    if last == "CREATED":
        return True, ""
    return False, last.replace("NOT CREATED:", "").strip()
