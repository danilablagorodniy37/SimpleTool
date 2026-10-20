"""Portable build: a single SimpleTool.exe that does not need Python installed.

Run from the repository root:
    python build.py

The result is dist/SimpleTool.exe. Copy it to a USB stick and run it on any Windows 10/11 PC.
The program data (snapshots, backups, settings) stays on each computer in
%LOCALAPPDATA%\\SimpleTool: a snapshot describes one particular PC and must not travel to another one.
"""
import hashlib
import os
import re
import subprocess
import sys

PYINSTALLER = "6.22.3"  # pinned version: the build is reproducible on any computer
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
    if exe_is_locked(os.path.join(DIST, "SimpleTool.exe")):
        sys.exit("dist\\SimpleTool.exe is running. Close SimpleTool and run build.py again.")
    version = app_version()
    numbers = tuple((int(n) for n in (version.split(".") + ["0", "0", "0"])[:4]))
    os.makedirs(BUILD, exist_ok=True)
    version_file = os.path.join(BUILD, "version_info.txt")
    with open(version_file, "w", encoding="utf-8") as f:
        f.write(VERSION_INFO.format(numbers=numbers, version=version))

    # Absolute paths: PyInstaller resolves relative paths from the spec file folder (build/)
    subprocess.run([
        python_with_pyinstaller(), "-m", "PyInstaller", "--noconfirm", "--clean", "--onefile", "--windowed",
        "--name", "SimpleTool",
        "--icon", os.path.join(ROOT, "assets", "app.ico"),
        "--add-data", os.path.join(ROOT, "assets") + os.pathsep + "assets",
        "--version-file", version_file,
        "--distpath", DIST, "--workpath", os.path.join(BUILD, "work"), "--specpath", BUILD,
        os.path.join(ROOT, "main.py"),
    ], cwd=ROOT, check=True)

    exe = os.path.join(DIST, "SimpleTool.exe")
    with open(exe, "rb") as f:
        digest = hashlib.sha256(f.read()).hexdigest()
    print(f"\nSimpleTool {version}: {exe}\n{os.path.getsize(exe) / 1024 / 1024:.1f} MB, SHA256 {digest}")


if __name__ == "__main__":
    main()
