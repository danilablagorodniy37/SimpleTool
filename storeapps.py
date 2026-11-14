"""Microsoft Store apps of this account: the ones a person sees in Start, with their own names and logos.

Windows lists the packages of an account with Get-AppxPackage; their names, publishers and logos are in each app's
AppxManifest.xml, where a name is often a reference into the app's resources ("ms-resource:AppName") that
SHLoadIndirectString turns into text in the language of Windows. Only apps with an entry in Start are offered:
frameworks, codecs, language packs, shell extensions of desktop programs and the parts of Windows that come as
packages are not. The packages Windows itself relies on (the Store, Windows Security, App Installer, the shell) are
never offered, whatever their manifests say.

An app is removed for this account with Remove-AppxPackage; Windows deletes its data folder itself, and the app can
be installed again from Microsoft Store. A restore point does not bring Store apps back, so none is made.
"""
import ctypes
import datetime
import json
import os
import re
import subprocess
from ctypes import wintypes
from xml.etree import ElementTree

import engine
import raster
import uninstaller

# Packages never offered for removal: Windows, the Store, security, sign-in and the runtimes apps share. Prefixes of
# the package name, compared in lower case
PROTECTED = ("microsoft.windowsstore", "microsoft.storepurchaseapp", "microsoft.desktopappinstaller",
             "microsoft.sechealthui", "microsoft.windows.sechealthui", "microsoft.vclibs", "microsoft.ui.xaml",
             "microsoft.net.", "microsoft.windowsappruntime", "microsoftcorporationii.winappruntime",
             "microsoft.services.store.engagement", "microsoft.xboxidentityprovider", "microsoft.gamingservices",
             "microsoft.aad.brokerplugin", "microsoft.accountscontrol", "microsoft.microsoftedge",
             "microsoft.languageexperiencepack", "microsoft.winget.source", "microsoft.widgetsplatformruntime",
             "microsoft.startexperiencesapp", "microsoft.applicationcompatibilityenhancements",
             "microsoftwindows.", "windows.")
SIGNATURE_SYSTEM = 4  # SignatureKind: 0 None, 1 Developer, 2 Enterprise, 3 Store, 4 System
FULL_NAME = re.compile(r"^[A-Za-z0-9.\-]+_[A-Za-z0-9.\-]+_[A-Za-z0-9\-]*_[A-Za-z0-9.\-~]*_[a-z0-9]+$")
LIST_SCRIPT = ("[Console]::OutputEncoding = [Text.Encoding]::UTF8; "
               "Get-AppxPackage | Select-Object Name, PackageFullName, PackageFamilyName, InstallLocation, Version, "
               "SignatureKind, IsFramework, IsResourcePackage, IsBundle, NonRemovable | ConvertTo-Json -Compress")
POWERSHELL_TIMEOUT = 120  # seconds; a removal of a large app takes a while
LOGO_SIZES = re.compile(r"\.(?:targetsize-(\d+)|scale-(\d+))", re.IGNORECASE)


class StoreApp:
    """One Microsoft Store app of this account. It has the fields of uninstaller.Program the Programs page shows."""

    def __init__(self, name, full_name, family, title, publisher="", version="", size=0, installed=None,
                 location="", logo=None):
        self.key = "appx:" + family  # stays the same when the app is updated
        self.package = name          # its package name: Microsoft.WindowsCalculator
        self.full_name = full_name   # name, version, processor and publisher ID: what Remove-AppxPackage takes
        self.family = family
        self.name = title            # its own name, as Start shows it
        self.publisher = publisher
        self.version = version
        self.size = size             # bytes of its install folder
        self.installed = installed   # the date its current version was installed, or None
        self.location = location
        self.logo = logo             # the image file of its logo, or None

    def __repr__(self):
        return f"StoreApp({self.name!r}, {self.full_name!r})"


def protected(name):
    return name.lower().startswith(PROTECTED)


def _powershell(script):
    """Runs a PowerShell script given as plain text (an encoded command looks like malware to antivirus programs)
    and returns (exit code, output, errors)."""
    try:
        result = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
                                stdin=subprocess.DEVNULL, capture_output=True, timeout=POWERSHELL_TIMEOUT,
                                creationflags=engine.CREATE_NO_WINDOW, env=engine.clean_env())
    except subprocess.TimeoutExpired:
        raise OSError(f"PowerShell did not finish in {POWERSHELL_TIMEOUT} s") from None
    return (result.returncode, result.stdout.decode("utf-8", "replace"),
            result.stderr.decode("utf-8", "replace") or result.stdout.decode("utf-8", "replace"))


def _packages():
    """Get-AppxPackage of this account as a list of dicts."""
    code, output, errors = _powershell(LIST_SCRIPT)
    output = output.strip().lstrip("﻿")
    if code or not output:
        raise OSError(errors.strip() or f"Get-AppxPackage exited with code {code}")
    data = json.loads(output)
    return [data] if isinstance(data, dict) else data


def _local(tag):
    return tag.rpartition("}")[2]


def resource_uris(name, text):
    """Where a manifest's "ms-resource:" text can point, in the order to try."""
    key = text[len("ms-resource:"):]
    if key.startswith("//"):
        return [text]
    if key.startswith("/"):
        return [f"ms-resource://{name}{key}"]
    if "/" in key:
        return [f"ms-resource://{name}/{key}", f"ms-resource://{name}/Resources/{key}"]
    return [f"ms-resource://{name}/Resources/{key}", f"ms-resource://{name}/{key}"]


def resolve(full_name, name, text):
    """A manifest's text: itself, or the resource it names in the language of Windows; "" if it cannot be read."""
    text = (text or "").strip()
    if not text.lower().startswith("ms-resource:"):
        return text
    shlwapi = ctypes.windll.shlwapi
    shlwapi.SHLoadIndirectString.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.UINT, ctypes.c_void_p]
    buffer = ctypes.create_unicode_buffer(1024)
    for uri in resource_uris(name, text):
        if shlwapi.SHLoadIndirectString(f"@{{{full_name}?{uri}}}", buffer, len(buffer), None) == 0 and buffer.value:
            return buffer.value
    return ""


def read_manifest(location):
    """(properties, [visual elements of each app]) of an app's AppxManifest.xml, or None if it cannot be read."""
    try:
        root = ElementTree.parse(os.path.join(location, "AppxManifest.xml")).getroot()
    except (OSError, ElementTree.ParseError):
        return None
    properties = {_local(item.tag): (item.text or "").strip()
                  for part in root if _local(part.tag) == "Properties" for item in part}
    visuals = []
    for part in root:
        if _local(part.tag) != "Applications":
            continue
        for application in part:
            for item in application:
                if _local(item.tag) == "VisualElements":
                    visuals.append(dict(item.attrib))
    return properties, visuals


def in_start(visuals):
    """Whether one of the apps of a package has an entry in Start (AppListEntry="none" hides it)."""
    return any((visual.get("AppListEntry") or "default").lower() != "none" for visual in visuals)


def logo_file(location, relative, size=32):
    """The best file for a logo the manifest names (Assets\\AppList.png): the variant drawn for a size at least as
    big as size without a plate (targetsize-N_altform-unplated), else the largest scale variant up to 200 %,
    else the file itself. High contrast variants are left out. None if there is none."""
    if not relative:
        return None
    path = os.path.join(location, relative.replace("/", "\\"))
    folder, file = os.path.split(path)
    stem, ext = os.path.splitext(file)
    try:
        names = os.listdir(folder)
    except OSError:
        return None
    best, best_rank = None, None
    for candidate in names:
        low = candidate.lower()
        if not (low.startswith(stem.lower() + ".") and low.endswith(ext.lower())) or "contrast-" in low:
            continue
        sizes = LOGO_SIZES.findall(candidate)
        target = next((int(t) for t, _ in sizes if t), None)
        scale = next((int(s) for _, s in sizes if s), None)
        unplated = "altform-unplated" in low
        if "altform-" in low and not unplated:
            continue  # light-unplated and the like are drawn for other backgrounds
        if target:
            rank = (0 if unplated else 1, 0 if target >= size else 1, abs(target - size))
        elif scale:
            rank = (2, 0 if scale <= 200 else 1, -scale if scale <= 200 else scale)
        elif low == file.lower():
            rank = (3, 0, 0)
        else:
            continue
        if best_rank is None or rank < best_rank:
            best, best_rank = os.path.join(folder, candidate), rank
    return best


def _date(path):
    try:
        return datetime.date.fromtimestamp(os.path.getctime(path))
    except (OSError, ValueError, OverflowError):
        return None


def installed_apps(sizes=True):
    """The Store apps of this account a person can remove, by name. None when SimpleTool runs as another account
    than the one signed in: Get-AppxPackage would list the other account's apps."""
    if engine.other_account():
        return None
    apps = []
    for package in _packages():
        name, location = package.get("Name") or "", package.get("InstallLocation") or ""
        full_name = package.get("PackageFullName") or ""
        if (package.get("IsFramework") or package.get("IsResourcePackage") or package.get("IsBundle")
                or package.get("NonRemovable") or package.get("SignatureKind") == SIGNATURE_SYSTEM
                or not location or not FULL_NAME.match(full_name) or protected(name)):
            continue
        manifest = read_manifest(location)
        if manifest is None:
            continue
        properties, visuals = manifest
        if not in_start(visuals):
            continue
        title = resolve(full_name, name, properties.get("DisplayName")) or next(
            (resolve(full_name, name, v.get("DisplayName")) for v in visuals if v.get("DisplayName")), "") or name
        visible = next((v for v in visuals if (v.get("AppListEntry") or "default").lower() != "none"), {})
        logo = logo_file(location, visible.get("Square44x44Logo")) or logo_file(location, properties.get("Logo"))
        version = package.get("Version") or ""
        if isinstance(version, dict):  # an older PowerShell writes the Version object, not its text
            version = ".".join(str(version.get(part, 0)) for part in ("Major", "Minor", "Build", "Revision"))
        apps.append(StoreApp(name, full_name, package.get("PackageFamilyName") or name, title,
                             resolve(full_name, name, properties.get("PublisherDisplayName")), version,
                             uninstaller.folder_size(location) if sizes else 0, _date(location), location, logo))
    return sorted(apps, key=lambda app: app.name.lower())


def logo_png(path, size=32):
    """A logo image file scaled to fit size x size pixels, centred, with its transparency, as a PNG; None if GDI+
    cannot read it. Tk can read a PNG but not scale it smoothly, so GDI+ draws it."""
    try:
        lib = raster._library()
    except OSError:
        return None
    lib.GdipCreateBitmapFromFile.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(ctypes.c_void_p)]
    lib.GdipGetImageWidth.argtypes = lib.GdipGetImageHeight.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint)]
    lib.GdipSetInterpolationMode.argtypes = [ctypes.c_void_p, ctypes.c_int]
    lib.GdipDrawImageRectI.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                       ctypes.c_int]
    image, bitmap, graphics = ctypes.c_void_p(), ctypes.c_void_p(), ctypes.c_void_p()
    try:
        if lib.GdipCreateBitmapFromFile(path, ctypes.byref(image)):
            return None
        width, height = ctypes.c_uint(), ctypes.c_uint()
        lib.GdipGetImageWidth(image, ctypes.byref(width))
        lib.GdipGetImageHeight(image, ctypes.byref(height))
        if not width.value or not height.value:
            return None
        scale = size / max(width.value, height.value)
        w, h = max(1, round(width.value * scale)), max(1, round(height.value * scale))
        if lib.GdipCreateBitmapFromScan0(size, size, 0, raster.PIXEL_FORMAT_32BPP_ARGB, None, ctypes.byref(bitmap)):
            return None
        if lib.GdipGetImageGraphicsContext(bitmap, ctypes.byref(graphics)):
            return None
        lib.GdipGraphicsClear(graphics, 0)
        lib.GdipSetInterpolationMode(graphics, 7)  # high quality bicubic
        lib.GdipSetPixelOffsetMode(graphics, raster.PIXEL_OFFSET_HALF)
        if lib.GdipDrawImageRectI(graphics, image, (size - w) // 2, (size - h) // 2, w, h):
            return None
        data = raster._BitmapData()
        rect = raster._Rect(0, 0, size, size)
        if lib.GdipBitmapLockBits(bitmap, ctypes.byref(rect), raster.LOCK_READ, raster.PIXEL_FORMAT_32BPP_ARGB,
                                  ctypes.byref(data)):
            return None
        try:
            raw = ctypes.string_at(data.Scan0, data.Stride * size)
        finally:
            lib.GdipBitmapUnlockBits(bitmap, ctypes.byref(data))
        pixels = b"".join(raw[y * data.Stride:y * data.Stride + size * 4] for y in range(size))
        rgba = bytearray(pixels)
        rgba[0::4], rgba[2::4] = pixels[2::4], pixels[0::4]  # BGRA -> RGBA
        return raster.png(size, size, bytes(rgba))
    finally:
        if graphics:
            lib.GdipDeleteGraphics(graphics)
        for handle in (bitmap, image):
            if handle:
                lib.GdipDisposeImage(handle)


def remove(app):
    """Removes an app for this account. Raises OSError with Windows' message if Remove-AppxPackage fails."""
    if not FULL_NAME.match(app.full_name) or protected(app.package):
        raise ValueError(f"not a removable package: {app.full_name}")
    # The full name has only letters, digits, dots, dashes, tildes and underscores, so it is safe inside quotes
    code, output, errors = _powershell(f"Remove-AppxPackage -Package '{app.full_name}' -ErrorAction Stop")
    if code:
        raise OSError(errors.strip().splitlines()[0] if errors.strip() else f"Remove-AppxPackage exited with code {code}")


def still_installed(app):
    """Whether the app is still among this account's packages, in any version."""
    return any(package.get("PackageFamilyName") == app.family for package in _packages())
