"""Обзор служб Windows: тип запуска из реестра и текущее состояние через диспетчер служб."""
import ctypes
from ctypes import wintypes

from engine import read_value

# (группа, имя службы, id твика, который её меняет)
SERVICES = [
    ("telemetry", "DiagTrack", "telemetry"),
    ("telemetry", "dmwappushservice", "telemetry"),
    ("telemetry", "diagnosticshub.standardcollector.service", None),
    ("telemetry", "WerSvc", None),
    ("telemetry", "PcaSvc", None),
    ("telemetry", "NvTelemetryContainer", "nvidia"),
    ("telemetry", "wisvc", None),
    ("telemetry", "RetailDemo", None),
    ("location", "lfsvc", "location"),
    ("location", "MapsBroker", None),
    ("performance", "SysMain", None),
    ("performance", "WSearch", None),
    ("performance", "Spooler", None),
    ("performance", "Fax", None),
    ("gaming", "XblAuthManager", None),
    ("gaming", "XblGameSave", None),
    ("gaming", "XboxNetApiSvc", None),
    ("gaming", "XboxGipSvc", None),
    ("security", "WinDefend", None),
    ("security", "mpssvc", None),
    ("security", "wuauserv", None),
    ("security", "RemoteRegistry", None),
    ("security", "Schedule", None),
    ("security", "EventLog", None),
]
GROUPS = ["telemetry", "location", "performance", "gaming", "security"]

SC_MANAGER_CONNECT = 0x0001
SERVICE_QUERY_STATUS = 0x0004
ERROR_ACCESS_DENIED = 5
ERROR_SERVICE_DOES_NOT_EXIST = 1060


class SERVICE_STATUS(ctypes.Structure):
    _fields_ = [(name, wintypes.DWORD) for name in (
        "dwServiceType", "dwCurrentState", "dwControlsAccepted", "dwWin32ExitCode",
        "dwServiceSpecificExitCode", "dwCheckPoint", "dwWaitHint")]


_advapi = ctypes.WinDLL("advapi32", use_last_error=True)
_advapi.OpenSCManagerW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD]
_advapi.OpenSCManagerW.restype = wintypes.HANDLE
_advapi.OpenServiceW.argtypes = [wintypes.HANDLE, wintypes.LPCWSTR, wintypes.DWORD]
_advapi.OpenServiceW.restype = wintypes.HANDLE
_advapi.QueryServiceStatus.argtypes = [wintypes.HANDLE, ctypes.POINTER(SERVICE_STATUS)]
_advapi.QueryServiceStatus.restype = wintypes.BOOL
_advapi.CloseServiceHandle.argtypes = [wintypes.HANDLE]
_advapi.CloseServiceHandle.restype = wintypes.BOOL


class ServiceState:
    """state: on / off / missing / unknown; start: 0–4 или None; running: 1–7 или None; reason — почему неизвестно."""

    def __init__(self, name):
        self.name = name
        self.state = "unknown"
        self.start = None
        self.delayed = False
        self.running = None
        self.reason = None


def _query_running(scm, info):
    handle = _advapi.OpenServiceW(scm, info.name, SERVICE_QUERY_STATUS)
    if not handle:
        error = ctypes.get_last_error()
        if error == ERROR_SERVICE_DOES_NOT_EXIST:
            info.state = "missing"
        elif error == ERROR_ACCESS_DENIED:
            info.reason = info.reason or "access_denied"
        else:
            info.reason = info.reason or "error"
        return
    try:
        status = SERVICE_STATUS()
        if _advapi.QueryServiceStatus(handle, ctypes.byref(status)):
            info.running = status.dwCurrentState
        else:
            info.reason = info.reason or "error"
    finally:
        _advapi.CloseServiceHandle(handle)


def scan_service(scm, name):
    info = ServiceState(name)
    path = rf"HKLM\SYSTEM\CurrentControlSet\Services\{name}"
    try:
        start = read_value(path, "Start")
        if start is not None:
            info.start = start[0]
            delayed = read_value(path, "DelayedAutostart")
            info.delayed = bool(delayed and delayed[0])
    except PermissionError:
        info.reason = "access_denied"
    except OSError:
        info.reason = "error"
    if scm:
        _query_running(scm, info)
    else:
        info.reason = info.reason or "scm_unavailable"
    if info.state == "missing":
        info.reason = None
    elif info.start is not None:
        info.state = "off" if info.start == 4 else "on"
    elif info.running not in (None, 1):
        info.state = "on"  # тип запуска не прочитать, но служба работает — значит, включена
    elif info.reason is None and info.running is None:
        info.state = "missing"  # нет ни раздела в реестре, ни службы
    return info


def scan():
    """Словарь «имя службы -> ServiceState» для всех служб обзора."""
    scm = _advapi.OpenSCManagerW(None, None, SC_MANAGER_CONNECT)
    try:
        return {name: scan_service(scm, name) for _, name, _ in SERVICES}
    finally:
        if scm:
            _advapi.CloseServiceHandle(scm)
