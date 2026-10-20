"""Programs installed on this PC, for the list on the Memory limiter page.

Sources (read-only): Start menu shortcuts, entries of the installed programs list and known
Microsoft Store apps. Each program needs its process name, because the limiter works by process name.
"""
import glob
import os
import re
import struct
import winreg

import limiter

# Programs whose memory is used by a different process than the one the shortcut starts
ALIASES = {"steam": "steamwebhelper", "ealauncher": "eadesktop", "ubisoftconnect": "upc"}

# Microsoft Store apps: package name prefix -> (process, title)
STORE = {"MSTeams_": ("ms-teams", "Microsoft Teams"), "SpotifyAB.SpotifyMusic_": ("spotify", "Spotify"),
         "TelegramMessengerLLP.TelegramDesktop_": ("telegram", "Telegram"), "AppleInc.iTunes_": ("itunes", "iTunes")}

# Installers, uninstallers, updaters and help are not programs that use memory
SKIP_EXE = re.compile(r"unins|setup|install|inst$|updat|crash|errorreport|repair|readme|launchdevcmd", re.IGNORECASE)
SKIP_TITLE = re.compile(r"uninstall|удалить|видалити|readme|help|manual|documentation|website|license|release notes",
                        re.IGNORECASE)

UNINSTALL = [(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
             (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
             (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall")]
PACKAGES = r"Software\Classes\Local Settings\Software\Microsoft\Windows\CurrentVersion\AppModel\Repository\Packages"


def shortcut_target(data):
    """The path a .lnk shortcut points to and its arguments (MS-SHLLINK format). (None, None) if there is no path."""
    if len(data) < 0x4C or struct.unpack_from("<I", data, 0)[0] != 0x4C:
        return None, None
    flags = struct.unpack_from("<I", data, 0x14)[0]
    pos, target, args = 0x4C, None, None
    if flags & 0x1:  # HasLinkTargetIDList
        pos += 2 + struct.unpack_from("<H", data, pos)[0]
    if flags & 0x2:  # HasLinkInfo: local path to the target
        start = pos
        size, header, info_flags, _, base = struct.unpack_from("<IIIII", data, pos)
        if info_flags & 1:
            if header >= 0x24:  # Unicode path
                offset = start + struct.unpack_from("<I", data, pos + 0x1C)[0]
                end = offset
                while data[end:end + 2] != b"\0\0":
                    end += 2
                target = data[offset:end].decode("utf-16-le")
            else:
                target = data[start + base:data.index(b"\0", start + base)].decode("mbcs")
        pos = start + size
    unicode = flags & 0x80
    for bit in (0x4, 0x8, 0x10, 0x20):  # name, relative path, working directory, arguments
        if flags & bit:
            count = struct.unpack_from("<H", data, pos)[0]
            length = count * (2 if unicode else 1)
            text = data[pos + 2:pos + 2 + length].decode("utf-16-le" if unicode else "mbcs")
            pos += 2 + length
            if bit == 0x20:
                args = text
    return target, args


def process_for(path, args=None):
    """The process name of a program from the path to its .exe, or None if it is not a program for the list."""
    if not path or not path.lower().endswith(".exe"):
        return None
    windows = os.environ.get("SystemRoot", r"C:\Windows").lower()
    folder = os.path.normcase(os.path.dirname(path))
    if folder.startswith(os.path.normcase(windows) + os.sep) or "package cache" in folder:
        return None  # built-in Windows tools and cached installers
    name = limiter.normalize(path)
    # Squirrel apps (Discord, Slack, GitHub Desktop) start through Update.exe --processStart Name.exe
    match = re.search(r'--processStart\s+"?([^"]+?\.exe)', args or "", re.IGNORECASE)
    if match:
        name = limiter.normalize(match.group(1))
    elif args or SKIP_EXE.search(name):
        return None  # a shortcut with arguments is a special mode of the program or a service command
    name = ALIASES.get(name, name)
    return None if limiter.is_protected(name) else name


def _shortcuts():
    roots = [os.path.join(os.environ.get(var, ""), "Microsoft", "Windows", "Start Menu", "Programs")
             for var in ("ProgramData", "AppData")]
    for root in roots:
        for path in glob.glob(os.path.join(glob.escape(root), "**", "*.lnk"), recursive=True):
            title = os.path.splitext(os.path.basename(path))[0]
            if SKIP_TITLE.search(title):
                continue
            try:
                with open(path, "rb") as f:
                    target, args = shortcut_target(f.read())
            except (OSError, struct.error, ValueError, UnicodeDecodeError):
                continue
            yield title, target, args


def _values(key, *names):
    values = []
    for name in names:
        try:
            values.append(winreg.QueryValueEx(key, name)[0])
        except OSError:
            values.append(None)
    return values


def _uninstall_entries():
    for hive, path in UNINSTALL:
        try:
            root = winreg.OpenKey(hive, path)
        except OSError:
            continue
        with root:
            for i in range(winreg.QueryInfoKey(root)[0]):
                try:
                    with winreg.OpenKey(root, winreg.EnumKey(root, i)) as key:
                        title, icon, system, parent = _values(key, "DisplayName", "DisplayIcon", "SystemComponent",
                                                              "ParentKeyName")
                except OSError:
                    continue
                if not title or system == 1 or parent or not isinstance(icon, str):
                    continue  # components, updates and entries without a program icon
                yield title, icon.split(",")[0].strip().strip('"'), None


def _store_apps():
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, PACKAGES)
    except OSError:
        return
    with key:
        for i in range(winreg.QueryInfoKey(key)[0]):
            package = winreg.EnumKey(key, i)
            for prefix, (name, title) in STORE.items():
                if package.startswith(prefix):
                    yield name, title


def installed(exists=os.path.isfile):
    """[(process, title)] alphabetically. Slow if drives are asleep, so call it from a background thread."""
    found = {}
    for title, target, args in list(_shortcuts()) + list(_uninstall_entries()):
        name = process_for(target, args)
        if name and name not in found and not SKIP_TITLE.search(title) and exists(target):
            found[name] = title.strip()
    for name, title in _store_apps():
        found.setdefault(name, title)
    return sorted(found.items(), key=lambda item: item[1].lower())
