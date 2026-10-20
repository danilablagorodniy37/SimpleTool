"""Portable build: a single SimpleTool.exe that does not need Python installed.

Run from the repository root:
    python build.py

The result is dist/SimpleTool.exe. Copy it to a USB stick and run it on any Windows 10/11 PC.
The program data (snapshots, backups, settings) stays on each computer in
%LOCALAPPDATA%\\SimpleTool: a snapshot describes one particular PC and must not travel to another one.

dist/THIRD-PARTY-NOTICES.txt lists the licences of what the exe contains (Python, Tcl/Tk, PyInstaller):
publish it together with the exe.
"""
import hashlib
import os
import re
import subprocess
import sys

PYINSTALLER = "6.22.3"  # pinned version: the build is reproducible on any computer
PYTHON = (3, 12)  # the version SimpleTool is tested with; the exe contains this Python
ROOT = os.path.dirname(os.path.abspath(__file__))
BUILD = os.path.join(ROOT, "build")
DIST = os.path.join(ROOT, "dist")
VENV = os.path.join(ROOT, ".build-venv")

VERSION_INFO = """VSVersionInfo(
  ffi=FixedFileInfo(filevers={numbers}, prodvers={numbers}, mask=0x3f, flags=0x0, OS=0x40004,
                    fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('040904B0', [
      StringStruct('CompanyName', 'blagotech'),
      StringStruct('FileDescription', 'SimpleTool - Windows tweaker (beta)'),
      StringStruct('FileVersion', '{version}'),
      StringStruct('InternalName', 'SimpleTool'),
      StringStruct('LegalCopyright', 'Copyright (c) 2024-2026 blagotech. Source code: MIT License'),
      StringStruct('OriginalFilename', 'SimpleTool.exe'),
      StringStruct('ProductName', 'SimpleTool'),
      StringStruct('ProductVersion', '{version} beta')])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"""


def app_version():
    with open(os.path.join(ROOT, "main.py"), encoding="utf-8") as f:
        return re.search(r'^VERSION = "([\d.]+)"', f.read(), re.MULTILINE).group(1)


def python_with_pyinstaller():
    """The current Python if it has the required PyInstaller version, otherwise a separate .build-venv."""
    try:
        import PyInstaller
        if PyInstaller.__version__ == PYINSTALLER:
            return sys.executable
    except ImportError:
        pass
    python = os.path.join(VENV, "Scripts", "python.exe")
    if not os.path.exists(python):
        subprocess.run([sys.executable, "-m", "venv", VENV], check=True)
    subprocess.run([python, "-m", "pip", "install", "--disable-pip-version-check", f"pyinstaller=={PYINSTALLER}"],
                   check=True)
    return python


NOTICES_HEADER = """SimpleTool.exe - third-party notices

SimpleTool is released under the MIT License (below). SimpleTool.exe is built with PyInstaller and contains
a copy of Python {python} with the libraries of its Windows build (Tcl/Tk, OpenSSL, libffi, bzip2, xz,
mpdecimal, zlib) and the PyInstaller bootloader and run-time hooks. Their licences follow.
"""


def write_notices(python, path):
    """THIRD-PARTY-NOTICES.txt: the licences of everything the exe contains, from the Python that builds it."""
    script = ("import importlib.metadata as m, os, platform, sys; d = m.distribution('pyinstaller'); "
              "print(platform.python_version()); print(os.path.join(sys.base_prefix, 'LICENSE.txt')); "
              "print(next(d.locate_file(f) for f in d.files if f.name == 'COPYING.txt'))")
    version, python_license, pyinstaller_license = subprocess.run(
        [python, "-c", script], capture_output=True, text=True, check=True).stdout.split("\n")[:3]
    parts = [NOTICES_HEADER.format(python=version)]
    for title, source in (("SimpleTool", os.path.join(ROOT, "LICENSE")), (f"Python {version}", python_license),
                          (f"PyInstaller {PYINSTALLER}", pyinstaller_license)):
        with open(source, encoding="utf-8") as f:
            parts.append(f"{'=' * 78}\n{title}\n{'=' * 78}\n\n{f.read().strip()}\n")
    with open(path, "w", encoding="utf-8", newline="\r\n") as f:
        f.write("\n\n".join(parts))


def exe_is_locked(path):
    """A running exe cannot be overwritten: better to say so right away than to fail at the end of the build."""
    if not os.path.exists(path):
        return False
    try:
        with open(path, "r+b"):
            return False
    except PermissionError:
        return True


def main():
    if sys.version_info[:2] != PYTHON:
        sys.exit(f"Build with Python {PYTHON[0]}.{PYTHON[1]}: the exe contains the Python that builds it.")
    if exe_is_locked(os.path.join(DIST, "SimpleTool.exe")):
        sys.exit("dist\\SimpleTool.exe is running. Close SimpleTool and run build.py again.")
    version = app_version()
    numbers = tuple((int(n) for n in (version.split(".") + ["0", "0", "0"])[:4]))
    os.makedirs(BUILD, exist_ok=True)
    version_file = os.path.join(BUILD, "version_info.txt")
    with open(version_file, "w", encoding="utf-8") as f:
        f.write(VERSION_INFO.format(numbers=numbers, version=version))

    # Absolute paths: PyInstaller resolves relative paths from the spec file folder (build/)
    python = python_with_pyinstaller()
    # --noupx: antivirus programs treat UPX-packed files as suspicious, and UPX is used whenever it is on PATH
    subprocess.run([
        python, "-m", "PyInstaller", "--noconfirm", "--clean", "--onefile", "--windowed", "--noupx",
        "--name", "SimpleTool",
        "--icon", os.path.join(ROOT, "assets", "app.ico"),
        "--add-data", os.path.join(ROOT, "assets") + os.pathsep + "assets",
        "--version-file", version_file,
        "--distpath", DIST, "--workpath", os.path.join(BUILD, "work"), "--specpath", BUILD,
        os.path.join(ROOT, "main.py"),
    ], cwd=ROOT, check=True)

    notices = os.path.join(DIST, "THIRD-PARTY-NOTICES.txt")
    write_notices(python, notices)
    exe = os.path.join(DIST, "SimpleTool.exe")
    with open(exe, "rb") as f:
        digest = hashlib.sha256(f.read()).hexdigest()
    print(f"\nSimpleTool {version}: {exe}\n{os.path.getsize(exe) / 1024 / 1024:.1f} MB, SHA256 {digest}\n{notices}")


if __name__ == "__main__":
    main()
