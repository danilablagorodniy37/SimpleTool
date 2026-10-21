"""Installing an update: download the new SimpleTool.exe, check it, put it in place of this one.

Only the portable exe updates itself; run from the source code, SimpleTool sends the user to the download page.

1. The file is downloaded from SimpleTool's own releases on GitHub, next to the running exe, as SimpleTool.exe.new.
2. Its size and SHA-256 must match the release (blagotech.uk/api/simpletool passes on GitHub's digest of the
   asset). Without a published SHA-256 nothing is installed: the user downloads by hand instead.
3. Windows cannot overwrite a running exe but can rename it: the running one becomes SimpleTool.exe.old, the new
   one takes its name. If anything fails on the way, the old one is put back.
4. The caller starts the new exe and exits. The new one deletes SimpleTool.exe.old (cleanup()).
"""
import hashlib
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request

# Downloads come only from SimpleTool's releases
RELEASES = "https://github.com/danilablagorodniy37/SimpleTool/releases/download/"
TIMEOUT = 60
CHUNK = 256 * 1024
MAX_SIZE = 200 * 1024 * 1024


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


def start(exe):
    """Starts the new version from its own folder, independent of this process."""
    subprocess.Popen([exe], cwd=os.path.dirname(exe), close_fds=True,
                     creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP)


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

