"""Ограничение памяти программ (Chrome, Discord и т. п.).

Два режима для каждой программы:
* мягкий — лимит на программу целиком: когда её процессы вместе занимают в оперативной памяти больше лимита,
  SimpleTool выгружает их рабочие наборы (EmptyWorkingSet), начиная с самых больших. Программа не падает,
  выгруженные страницы Windows подгружает обратно, когда они понадобятся;
* жёсткий — потолок Windows на каждый процесс программы (SetProcessWorkingSetSizeEx с жёстким максимумом).
  Потолки действуют, пока живёт процесс, и снимаются, когда ограничитель выключают или SimpleTool закрывается.

Ограничитель работает в фоновом потоке, пока открыт SimpleTool, в том числе свёрнутый в трей.
"""
import ctypes
import json
import os
import threading
import time
from ctypes import wintypes

import engine

MB = 1024 * 1024
MIN_LIMIT_MB = 100
MAX_LIMIT_MB = 65536
# Лимиты, по которым ходят кнопки «−» и «+»: до гигабайта по 100 МБ, дальше всё крупнее
LIMIT_STEPS = list(range(100, 1001, 100)) + [1280, 1536, 1792, 2048, 2560, 3072, 3584, 4096, 5120, 6144, 7168,
                                             8192, 10240, 12288, 16384, 24576, 32768, 49152, 65536]
CUSTOM_LIMIT = 1024
INTERVALS = [2, 5, 10, 30]
DEFAULT_INTERVAL = 5
SOFT_TARGET = 0.85  # после выгрузки программа должна занимать не больше 85 % лимита, чтобы не выгружать её каждый цикл

# Системные процессы и сам SimpleTool: ограничение памяти у них может подвесить Windows
PROTECTED = {
    "system", "idle", "registry", "smss", "csrss", "wininit", "winlogon", "services", "lsass", "lsaiso", "lsm",
    "svchost", "fontdrvhost", "dwm", "explorer", "sihost", "taskhostw", "ctfmon", "memory compression",
    "memcompression", "audiodg", "spoolsv", "msmpeng", "nissrv", "securityhealthservice", "sgrmbroker", "smartscreen",
    "conhost", "runtimebroker", "startmenuexperiencehost", "shellexperiencehost", "searchhost", "searchindexer",
    "textinputhost", "wudfhost", "dllhost", "simpletool", "python", "pythonw",
}

# (имя процесса, название, лимит по умолчанию в МБ)
PRESETS = [
    ("chrome", "Google Chrome", 2048), ("msedge", "Microsoft Edge", 2048), ("firefox", "Mozilla Firefox", 2048),
    ("brave", "Brave", 2048), ("opera", "Opera", 2048), ("vivaldi", "Vivaldi", 2048),
    ("browser", "Yandex Browser", 2048), ("discord", "Discord", 700),
    ("telegram", "Telegram", 500), ("steamwebhelper", "Steam", 800), ("spotify", "Spotify", 500),
    ("obs64", "OBS Studio", 1024), ("ms-teams", "Microsoft Teams", 1024), ("slack", "Slack", 800),
]
PRESET_NAMES = {name: title for name, title, _ in PRESETS}
PRESET_LIMITS = {name: limit for name, _, limit in PRESETS}


def normalize(name):
    """Имя процесса без пути и .exe в нижнем регистре: «Chrome.exe» -> «chrome»."""
    name = os.path.basename(name.strip()).lower()
    return name[:-4] if name.endswith(".exe") else name


def is_protected(name):
    return normalize(name) in PROTECTED


def clamp_limit(mb):
    return max(MIN_LIMIT_MB, min(MAX_LIMIT_MB, int(mb)))


# --- Windows API ---

class _ProcessEntry(ctypes.Structure):
    _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD), ("th32ProcessID", wintypes.DWORD),
                ("th32DefaultHeapID", ctypes.c_void_p), ("th32ModuleID", wintypes.DWORD),
                ("cntThreads", wintypes.DWORD), ("th32ParentProcessID", wintypes.DWORD),
                ("pcPriClassBase", ctypes.c_long), ("dwFlags", wintypes.DWORD), ("szExeFile", ctypes.c_wchar * 260)]


class _MemoryCounters(ctypes.Structure):
    _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + [
        (name, ctypes.c_size_t) for name in (
            "PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage", "QuotaPagedPoolUsage",
            "QuotaPeakNonPagedPoolUsage", "QuotaNonPagedPoolUsage", "PagefileUsage", "PeakPagefileUsage",
            "PrivateUsage")]


class WindowsApi:
    """Тонкая обёртка над kernel32: в тестах её подменяет поддельная реализация."""

    QUERY = 0x1000       # PROCESS_QUERY_LIMITED_INFORMATION
    SET_QUOTA = 0x0100   # PROCESS_SET_QUOTA
    MAX_ENABLE, MIN_DISABLE, MAX_DISABLE = 0x4, 0x2, 0x8

    def __init__(self):
        k = ctypes.WinDLL("kernel32", use_last_error=True)
        k.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
        k.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
        k.Process32FirstW.argtypes = k.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(_ProcessEntry)]
        k.OpenProcess.restype = wintypes.HANDLE
        k.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        k.CloseHandle.argtypes = [wintypes.HANDLE]
        k.K32GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(_MemoryCounters), wintypes.DWORD]
        k.K32EmptyWorkingSet.argtypes = [wintypes.HANDLE]
        k.SetProcessWorkingSetSizeEx.argtypes = [wintypes.HANDLE, ctypes.c_size_t, ctypes.c_size_t, wintypes.DWORD]
        k.GetProcessWorkingSetSizeEx.argtypes = [wintypes.HANDLE, ctypes.POINTER(ctypes.c_size_t),
                                                 ctypes.POINTER(ctypes.c_size_t), ctypes.POINTER(wintypes.DWORD)]
        self.k = k

    def processes(self):
        """[(pid, имя процесса без .exe)]"""
        snapshot = self.k.CreateToolhelp32Snapshot(0x2, 0)  # TH32CS_SNAPPROCESS
        if not snapshot or snapshot == wintypes.HANDLE(-1).value:
            return []
        try:
            entry = _ProcessEntry()
            entry.dwSize = ctypes.sizeof(entry)
            result, ok = [], self.k.Process32FirstW(snapshot, ctypes.byref(entry))
            while ok:
                result.append((entry.th32ProcessID, normalize(entry.szExeFile)))
                ok = self.k.Process32NextW(snapshot, ctypes.byref(entry))
            return result
        finally:
            self.k.CloseHandle(snapshot)

    def _open(self, pid, access):
        return self.k.OpenProcess(access, False, pid)

    def working_set(self, pid):
        """Сколько процесс занимает в оперативной памяти (байт) или None, если доступа нет."""
        handle = self._open(pid, self.QUERY)
        if not handle:
            return None
        try:
            counters = _MemoryCounters()
            counters.cb = ctypes.sizeof(counters)
            if not self.k.K32GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
                return None
            return counters.WorkingSetSize
        finally:
            self.k.CloseHandle(handle)

    def trim(self, pid):
        handle = self._open(pid, self.QUERY | self.SET_QUOTA)
        if not handle:
            return False
        try:
            return bool(self.k.K32EmptyWorkingSet(handle))
        finally:
            self.k.CloseHandle(handle)

    def _quota(self, handle):
        low, high, flags = ctypes.c_size_t(), ctypes.c_size_t(), wintypes.DWORD()
        if not self.k.GetProcessWorkingSetSizeEx(handle, ctypes.byref(low), ctypes.byref(high), ctypes.byref(flags)):
            return None
        return low.value, high.value, flags.value

    def set_hard_limit(self, pid, limit_bytes):
        handle = self._open(pid, self.QUERY | self.SET_QUOTA)
        if not handle:
            return False
        try:
            quota = self._quota(handle)
            if quota is None:
                return False
            low = min(quota[0], limit_bytes // 2)
            return bool(self.k.SetProcessWorkingSetSizeEx(handle, low, limit_bytes, self.MAX_ENABLE | self.MIN_DISABLE))
        finally:
            self.k.CloseHandle(handle)

    def clear_hard_limit(self, pid):
        handle = self._open(pid, self.QUERY | self.SET_QUOTA)
        if not handle:
            return False  # процесс уже завершился — вместе с ним исчез и потолок
        try:
            quota = self._quota(handle)
            if quota is None:
                return False
            return bool(self.k.SetProcessWorkingSetSizeEx(handle, quota[0], quota[1], self.MAX_DISABLE | self.MIN_DISABLE))
        finally:
            self.k.CloseHandle(handle)


# --- Настройки ---

def config_path():
    return os.path.join(engine.data_dir(), "limiter.json")


def default_config():
    return {"enabled": False, "interval": DEFAULT_INTERVAL, "rules": []}


def load_config():
    try:
        with open(config_path(), encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return default_config()
    config = default_config()
    config["enabled"] = bool(data.get("enabled", False))
    config["interval"] = data.get("interval") if data.get("interval") in INTERVALS else DEFAULT_INTERVAL
    seen = set()
    for rule in data.get("rules", []):
        try:
            name = normalize(str(rule["name"]))
            limit = clamp_limit(rule["limit_mb"])
        except (KeyError, TypeError, ValueError):
            continue
        if not name or name in seen or is_protected(name):
            continue  # повреждённый или опасный файл настроек не должен ограничить системный процесс
        seen.add(name)
        config["rules"].append({"name": name, "limit_mb": limit, "mode": "hard" if rule.get("mode") == "hard" else "soft",
                                "enabled": bool(rule.get("enabled", True))})
    return config


def save_config(config):
    tmp = config_path() + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=1)
    os.replace(tmp, config_path())


# --- Ограничитель ---

class Limiter:
    """Фоновый поток: раз в interval секунд проверяет программы из списка и держит их в пределах лимита."""

    def __init__(self, api=None, config=None):
        self.api = api or WindowsApi()
        self.config = config if config is not None else load_config()
        self.lock = threading.Lock()
        self.stats = {}     # имя -> {"count", "bytes", "denied", "largest", "freed", "trims"}
        self.capped = {}    # pid -> (имя, лимит в байтах): процессы, которым SimpleTool поставил жёсткий потолок
        self.freed_total = 0
        self.checked_at = None
        self.own_pid = os.getpid()
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._thread = None

    # Настройки меняет окно, поток читает их под той же блокировкой

    def update(self, change, save=True):
        """change(config) меняет настройки; изменения вступают в силу сразу."""
        with self.lock:
            change(self.config)
            if save:
                try:
                    save_config(self.config)
                except OSError:
                    pass  # не удалось записать файл: настройки всё равно действуют до выхода
        self._wake.set()

    def active(self):
        with self.lock:
            return self.config["enabled"] and any(rule["enabled"] for rule in self.config["rules"])

    def snapshot(self):
        with self.lock:
            return {"stats": {name: dict(s) for name, s in self.stats.items()}, "freed": self.freed_total,
                    "config": json.loads(json.dumps(self.config))}

    # Поток

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="memory-limiter", daemon=True)
        self._thread.start()

    def stop(self):
        """Останавливает поток и снимает все жёсткие потолки, которые ставил SimpleTool."""
        self._stop.set()
        self._wake.set()
        if self._thread:
            self._thread.join(timeout=5)
        self.release(list(self.capped))

    def _run(self):
        while not self._stop.is_set():
            try:
                self.cycle()
            except Exception:  # сбой одного цикла не должен останавливать ограничитель навсегда
                pass
            with self.lock:
                interval = self.config["interval"]
            self._wake.wait(interval)
            self._wake.clear()

    def release(self, pids):
        for pid in pids:
            if pid in self.capped:
                self.api.clear_hard_limit(pid)
                del self.capped[pid]

    def cycle(self):
        """Один проход: замер всех программ из списка и, если нужно, выгрузка памяти или потолки."""
        with self.lock:
            enabled = self.config["enabled"]
            rules = [dict(rule) for rule in self.config["rules"]]
        groups, names_by_pid = {}, {}
        for pid, name in self.api.processes():
            if pid != self.own_pid and pid > 4:
                groups.setdefault(name, []).append(pid)
                names_by_pid[pid] = name
        # Завершившиеся процессы забываем; номер, доставшийся другой программе, тоже не наш
        self.capped = {pid: value for pid, value in self.capped.items() if names_by_pid.get(pid) == value[0]}
        stats, freed = {}, 0
        for rule in rules:
            name, limit = rule["name"], rule["limit_mb"] * MB
            pids = groups.get(name, [])
            if is_protected(name):
                continue
            sizes = {pid: self.api.working_set(pid) for pid in pids}
            readable = {pid: size for pid, size in sizes.items() if size is not None}
            stat = {"count": len(pids), "bytes": sum(readable.values()), "denied": len(pids) - len(readable),
                    "largest": max(readable.values(), default=0), "freed": 0, "trims": 0}
            on = enabled and rule["enabled"]
            # Потолки снимаются, если программу выключили или перевели в мягкий режим
            if not on or rule["mode"] != "hard":
                self.release([pid for pid in pids if pid in self.capped])
            if on and rule["mode"] == "soft" and stat["bytes"] > limit:
                total = stat["bytes"]
                for pid in sorted(readable, key=readable.get, reverse=True):
                    if total <= limit * SOFT_TARGET:
                        break
                    if self.api.trim(pid):
                        after = self.api.working_set(pid)
                        if after is None:  # процесс завершился в эту секунду
                            continue
                        gained = max(0, readable[pid] - after)
                        total -= gained
                        readable[pid] = after
                        stat["freed"] += gained
                        stat["trims"] += 1
                stat["bytes"] = max(0, total)
                stat["largest"] = max(readable.values(), default=0)
            elif on and rule["mode"] == "hard":
                for pid in readable:
                    if self.capped.get(pid, (None, None))[1] != limit and self.api.set_hard_limit(pid, limit):
                        self.capped[pid] = (name, limit)
            freed += stat["freed"]
            stats[name] = stat
        # Программы, убранные из списка, не должны остаться с потолком
        names = {rule["name"] for rule in rules}
        self.release([pid for pid, (name, _) in list(self.capped.items()) if name not in names])
        with self.lock:
            self.stats = stats
            self.freed_total += freed
            self.checked_at = time.time()


def running_programs(api=None):
    """Запущенные программы для выбора: [(имя, процессов, байт)], самые «тяжёлые» первыми, без системных."""
    api = api or WindowsApi()
    totals = {}
    own = os.getpid()
    for pid, name in api.processes():
        if pid == own or pid <= 4 or is_protected(name):
            continue
        size = api.working_set(pid)
        count, total = totals.get(name, (0, 0))
        totals[name] = (count + 1, total + (size or 0))
    return sorted(((name, c, b) for name, (c, b) in totals.items()), key=lambda item: item[2], reverse=True)
