"""Песочница для тестов: SimpleTool работает как обычно, но не может изменить систему.

* Все пути реестра перенаправляются в HKCU\\Software\\SimpleToolTest\\<id>\\<HKLM|HKCU>\\...
* Любое открытие, создание или удаление раздела реестра за пределами песочницы роняет тест (растяжка).
* sc.exe и schtasks.exe подменяются: службы и задачи не трогаются, вызовы записываются.
* Ярлыки, снимки и резервные копии пишутся во временную папку; остальные внешние команды запрещены.
"""
import os
import shutil
import tempfile
import uuid
import winreg

import engine

SANDBOX_ROOT = r"Software\SimpleToolTest"


class SandboxEscape(AssertionError):
    """Код попытался выйти за пределы песочницы — в настоящей системе это изменило бы реестр."""


class GuardedWinreg:
    """Модуль winreg, который пропускает только разделы внутри песочницы."""

    def __init__(self, root):
        self.root = root.lower() + "\\"

    def _check(self, hive, sub):
        if hive != winreg.HKEY_CURRENT_USER or not (sub.lower() + "\\").startswith(self.root):
            raise SandboxEscape(f"registry access outside the sandbox: {hive} {sub}")

    def OpenKey(self, hive, sub, *args):
        self._check(hive, sub)
        return winreg.OpenKey(hive, sub, *args)

    def CreateKeyEx(self, hive, sub, *args):
        self._check(hive, sub)
        return winreg.CreateKeyEx(hive, sub, *args)

    def DeleteKeyEx(self, hive, sub, *args):
        self._check(hive, sub)
        return winreg.DeleteKeyEx(hive, sub, *args)

    def __getattr__(self, name):
        if name in ("ConnectRegistry", "OpenKeyEx", "CreateKey", "DeleteKey", "SaveKey", "LoadKey"):
            raise SandboxEscape(f"winreg.{name} is not allowed in tests")
        return getattr(winreg, name)


class FakeContext:
    """Состояние задач планировщика в песочнице (вместо Get-ScheduledTask)."""

    def __init__(self, sandbox):
        self.sandbox = sandbox

    @property
    def tasks(self):
        return dict(self.sandbox.tasks)


class Sandbox:
    def __init__(self):
        self.id = uuid.uuid4().hex[:10]
        self.root = rf"{SANDBOX_ROOT}\{self.id}"
        self.tmp = tempfile.mkdtemp(prefix="simpletool-test-")
        self.tasks = {}       # путь задачи в нижнем регистре -> отключена ли
        self.commands = []    # все вызовы sc.exe / schtasks.exe
        self._saved = []
        self.ctx = FakeContext(self)

    # --- пути ---

    def subkey(self, path):
        """Настоящий путь (HKLM\\... или HKCU\\...) -> раздел в песочнице."""
        hive, _, sub = path.partition("\\")
        return rf"{self.root}\{hive}" + (rf"\{sub}" if sub else "")

    # --- подмены ---

    def _patch(self, target, name, value):
        self._saved.append((target, name, getattr(target, name)))
        setattr(target, name, value)

    def start(self):
        self._patch(engine, "_split", lambda path: (winreg.HKEY_CURRENT_USER, self.subkey(path)))
        self._patch(engine, "winreg", GuardedWinreg(self.root))
        self._patch(engine, "run", self.fake_run)
        self._patch(engine, "powershell", self.forbidden)
        self._patch(engine, "data_dir", lambda: self.tmp)
        self._patch(engine, "desktop_dir", lambda: self.tmp)
        self._patch(engine, "create_shortcut", self.fake_shortcut)
        self._patch(engine, "notify_shell", lambda: None)
        self._patch(engine, "load_tasks", self.forbidden)
        # Корни разделов в настоящей Windows существуют всегда, их нельзя ни создать, ни удалить
        for hive in ("HKCU", "HKLM"):
            self.seed_key(hive)
        return self

    def stop(self):
        for target, name, value in reversed(self._saved):
            setattr(target, name, value)
        self._saved.clear()
        _delete_tree(winreg.HKEY_CURRENT_USER, self.root)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def __enter__(self):
        return self.start()

    def __exit__(self, *exc):
        self.stop()

    @staticmethod
    def forbidden(*args, **kwargs):
        raise SandboxEscape(f"external command is not allowed in tests: {args}")

    def fake_run(self, args):
        self.commands.append(list(args))
        program = os.path.basename(args[0]).lower()
        if program == "sc.exe" and len(args) == 3 and args[1] == "stop":
            return ""
        if program == "schtasks.exe" and len(args) == 5 and args[1] == "/change" and args[2] == "/tn":
            key = args[3].lower()
            if key not in self.tasks:
                raise RuntimeError(f"ERROR: The system cannot find the file specified. ({args[3]})")
            self.tasks[key] = args[4] == "/disable"
            return ""
        raise SandboxEscape(f"unexpected command: {args}")

    def fake_shortcut(self, lnk, target, args, icon):
        with open(lnk, "w", encoding="utf-8") as f:
            f.write(f"{target} {args} | {icon}")

    # --- подготовка и снимок состояния ---

    def seed_value(self, path, name, data, kind):
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, self.subkey(path), 0, winreg.KEY_WRITE) as key:
            winreg.SetValueEx(key, name, 0, kind, data)

    def seed_key(self, path):
        winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, self.subkey(path), 0, winreg.KEY_WRITE).Close()

    def state(self):
        """Всё, что SimpleTool может изменить: реестр песочницы, задачи, ярлыки."""
        registry = {}
        _dump(winreg.HKEY_CURRENT_USER, self.root, registry, len(self.root) + 1)
        shortcuts = sorted(f for f in os.listdir(self.tmp) if f.endswith(".lnk"))
        return {"registry": registry, "tasks": dict(self.tasks), "shortcuts": shortcuts}


def _dump(hive, sub, out, cut):
    try:
        key = winreg.OpenKey(hive, sub, 0, winreg.KEY_READ)
    except FileNotFoundError:
        return
    with key:
        subkeys, values, _ = winreg.QueryInfoKey(key)
        out[sub[cut:]] = {winreg.EnumValue(key, i)[0]: winreg.EnumValue(key, i)[1:] for i in range(values)}
        children = [winreg.EnumKey(key, i) for i in range(subkeys)]
    for child in children:
        _dump(hive, sub + "\\" + child, out, cut)


def _delete_tree(hive, sub):
    try:
        with winreg.OpenKey(hive, sub, 0, winreg.KEY_READ) as key:
            children = [winreg.EnumKey(key, i) for i in range(winreg.QueryInfoKey(key)[0])]
    except FileNotFoundError:
        return
    for child in children:
        _delete_tree(hive, sub + "\\" + child)
    winreg.DeleteKey(hive, sub)
