"""Installing an update: download the new SimpleTool.exe, check it, put it in place of this one.

Only the portable exe updates itself; run from the source code, SimpleTool sends the user to the download page.

1. The file is downloaded from SimpleTool's own releases on GitHub, next to the running exe, as SimpleTool.exe.new.
2. Its size and SHA-256 must match the release (blagotech.uk/api/simpletool passes on GitHub's digest of the
   asset). Without a published SHA-256 nothing is installed: the user downloads by hand instead.
3. Windows cannot overwrite a running exe but can rename it: the running one becomes SimpleTool.exe.old, the new
   one takes its name. If anything fails on the way, the old one is put back.
4. The caller starts the new exe and exits. The new one deletes SimpleTool.exe.old (cleanup()).

The portable exe is a PyInstaller onefile program: a small launcher unpacks it into a temporary _MEI folder and
runs it there, telling it where through environment variables. A copy started with those variables still set
takes itself for part of the running copy and runs from that copy's folder; the old launcher then cannot finish
and holds SimpleTool.exe.old. So every new copy starts with PYINSTALLER_RESET_ENVIRONMENT, which makes it unpack
itself anew (fresh_environment()). 0.6.3 started its update without it; needs_fresh_start() lets the new version
notice and start itself once more, properly.
"""
import ctypes
import hashlib
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from ctypes import wintypes

# Downloads come only from SimpleTool's releases
RELEASES = "https://github.com/danilablagorodniy37/SimpleTool/releases/download/"
TIMEOUT = 60
CHUNK = 256 * 1024
MAX_SIZE = 200 * 1024 * 1024
# Set in the environment of a copy SimpleTool starts itself: that copy never starts itself again
RESTARTED = "SIMPLETOOL_RESTARTED"


class UpdateFailed(Exception):
    """The update could not be installed; the running version is untouched."""


def target():
    """The running SimpleTool.exe, or None when running from the source code."""
    return os.path.abspath(sys.executable) if getattr(sys, "frozen", False) else None


def can_install(info):
    """Whether an update can install itself: the portable exe, a release asset and its published SHA-256."""
    return bool(target() and isinstance(info.get("url"), str) and info["url"].startswith(RELEASES)
                and re.fullmatch(r"[0-9a-f]{64}", info.get("sha256") or ""))


def download(url, path, sha256, size=None, progress=lambda done, total: None):
    """Downloads url to path and checks it. Raises UpdateFailed and leaves no file behind."""
    if not url.startswith(RELEASES):
        raise UpdateFailed("the update is not one of SimpleTool's releases")
    request = urllib.request.Request(url, headers={"User-Agent": "SimpleTool updater"})
    digest = hashlib.sha256()
    received = 0
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response, open(path, "wb") as f:
            total = size or int(response.headers.get("Content-Length") or 0) or None
            while True:
                chunk = response.read(CHUNK)
                if not chunk:
                    break
                received += len(chunk)
                if received > MAX_SIZE:
                    raise UpdateFailed("the download is far larger than SimpleTool")
                digest.update(chunk)
                f.write(chunk)
                progress(received, total)
    except UpdateFailed:
        _remove(path)
        raise
    except (urllib.error.URLError, OSError, ValueError) as exc:
        _remove(path)
        reason = getattr(exc, "reason", None) or exc
        raise UpdateFailed(f"the download failed: {reason}") from None
    if size and received != size:
        _remove(path)
        raise UpdateFailed(f"the download is incomplete ({received} of {size} bytes)")
    if digest.hexdigest() != sha256.lower():
        _remove(path)
        raise UpdateFailed("the downloaded file does not match the published SHA-256")


def replace(exe, new):
    """Puts new in place of the running exe; the old one stays as exe.old until the new one deletes it."""
    old = exe + ".old"
    _remove(old)  # left by an earlier update
    if os.path.exists(old):
        raise UpdateFailed(f"{old} is in use")
    try:
        os.replace(exe, old)
    except OSError as exc:
        _remove(new)
        raise UpdateFailed(f"SimpleTool.exe cannot be replaced: {exc}") from None
    try:
        os.replace(new, exe)
    except OSError as exc:
        os.replace(old, exe)  # put the running version back
        _remove(new)
        raise UpdateFailed(f"the new SimpleTool.exe cannot be put in place: {exc}") from None


def install(info, progress=lambda done, total: None):
    """Downloads and checks the update and puts it in place of the running exe. Returns the exe to start."""
    if not can_install(info):
        raise UpdateFailed("this update cannot install itself")
    exe = target()
    new = exe + ".new"
    download(info["url"], new, info["sha256"], info.get("size"), progress)
    replace(exe, new)
    return exe


def fresh_environment(environ=None):
    """The environment for a new copy of SimpleTool: it unpacks itself anew instead of joining this one."""
    env = dict(os.environ if environ is None else environ)
    env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
    env[RESTARTED] = "1"
    return env


def start(exe):
    """Starts the new version from its own folder, independent of this process."""
    subprocess.Popen([exe], cwd=os.path.dirname(exe), close_fds=True, env=fresh_environment(),
                     creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP)


class _ProcessEntry(ctypes.Structure):
    _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD), ("th32ProcessID", wintypes.DWORD),
                ("th32DefaultHeapID", ctypes.c_size_t), ("th32ModuleID", wintypes.DWORD),
                ("cntThreads", wintypes.DWORD), ("th32ParentProcessID", wintypes.DWORD),
                ("pcPriClassBase", ctypes.c_long), ("dwFlags", wintypes.DWORD), ("szExeFile", ctypes.c_wchar * 260)]


class _ModuleEntry(ctypes.Structure):
    _fields_ = [("dwSize", wintypes.DWORD), ("th32ModuleID", wintypes.DWORD), ("th32ProcessID", wintypes.DWORD),
                ("GlblcntUsage", wintypes.DWORD), ("ProccntUsage", wintypes.DWORD), ("modBaseAddr", ctypes.c_void_p),
                ("modBaseSize", wintypes.DWORD), ("hModule", wintypes.HMODULE), ("szModule", ctypes.c_wchar * 256),
                ("szExePath", ctypes.c_wchar * 260)]


def _parent_pid(kernel32):
    snapshot = kernel32.CreateToolhelp32Snapshot(0x2, 0)  # TH32CS_SNAPPROCESS
    if not snapshot or snapshot == wintypes.HANDLE(-1).value:
        return None
    try:
        entry = _ProcessEntry()
        entry.dwSize = ctypes.sizeof(entry)
        more = kernel32.Process32FirstW(snapshot, ctypes.byref(entry))
        while more:
            if entry.th32ProcessID == os.getpid():
                return entry.th32ParentProcessID
            more = kernel32.Process32NextW(snapshot, ctypes.byref(entry))
    finally:
        kernel32.CloseHandle(snapshot)
    return None


def parent_runs_python():
    """Whether the process that started this one has Python loaded; None if Windows does not say.

    A onefile exe started normally is the child of its own launcher, which has no Python in it. Started by a
    running SimpleTool with that copy's environment, it is the child of that copy, which has.
    """
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
        parent = _parent_pid(kernel32)
        if not parent:
            return None
        snapshot = kernel32.CreateToolhelp32Snapshot(0x8 | 0x10, parent)  # TH32CS_SNAPMODULE | SNAPMODULE32
        if not snapshot or snapshot == wintypes.HANDLE(-1).value:
            return None
        try:
            entry = _ModuleEntry()
            entry.dwSize = ctypes.sizeof(entry)
            more = kernel32.Module32FirstW(snapshot, ctypes.byref(entry))
            while more:
                name = entry.szModule.lower()
                if name.startswith("python3") and name.endswith(".dll"):
                    return True
                more = kernel32.Module32NextW(snapshot, ctypes.byref(entry))
            return False
        finally:
            kernel32.CloseHandle(snapshot)
    except (AttributeError, OSError):
        return None


def needs_fresh_start(frozen=None, parent_python=None, environ=None):
    """Whether this copy was started by an older SimpleTool with its environment (0.6.3's update) and runs from
    that copy's temporary folder. A copy SimpleTool started itself never asks again."""
    environ = os.environ if environ is None else environ
    frozen = bool(target()) if frozen is None else frozen
    if not frozen or environ.get(RESTARTED):
        return False
    return bool(parent_runs_python() if parent_python is None else parent_python)


def cleanup():
    """Deletes what an update left: the previous exe and an unfinished download. The previous exe may still be
    exiting, so it is tried again later by the caller if needed. Returns whether everything is gone."""
    exe = target()
    if not exe:
        return True
    for leftover in (exe + ".old", exe + ".new"):
        _remove(leftover)
    return not os.path.exists(exe + ".old")


def _remove(path):
    try:
        os.remove(path)
    except OSError:
        pass

