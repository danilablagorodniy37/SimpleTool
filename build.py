"""Сборка портативной версии: один SimpleTool.exe, которому не нужен установленный Python.

Запуск из корня репозитория:
    python build.py

Результат — dist/SimpleTool.exe. Его можно скопировать на флешку и запускать на любом Windows 10/11.
Данные программы (снимки, резервные копии, настройки) хранятся на каждом компьютере в
%LOCALAPPDATA%\\SimpleTool: снимок описывает конкретный ПК и не должен уезжать на флешке к другому.
"""
import hashlib
import os
import re
import subprocess
import sys

PYINSTALLER = "6.22.3"  # закреплённая версия: сборка повторяется одинаково на любом компьютере
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
    """Текущий Python, если в нём нужная версия PyInstaller, иначе отдельное окружение .build-venv."""
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
    """Запущенный exe нельзя перезаписать — лучше сказать об этом сразу, а не падать в конце сборки."""
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

    # Пути абсолютные: PyInstaller считает относительные пути от папки со spec-файлом (build/)
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
