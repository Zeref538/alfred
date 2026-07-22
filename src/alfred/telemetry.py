"""The instruments: what the machine is doing while Alfred serves it.

CPU, memory and storage come from Windows itself through ctypes — no
dependency, the same approach the hotkey uses. The GPU is the awkward one: it
has no simple call, so it is read from the performance counters through
PowerShell, which is slow enough to want its own slower cadence and a cached
answer in between.

Nothing here reaches the network, and nothing is stored. These are gauges: they
are read, shown, and forgotten.
"""

import ctypes
import shutil
import subprocess
import threading
import time
from ctypes import wintypes

CPU_INTERVAL = 1.0
# The GPU counter is read by spawning PowerShell, which takes about four
# seconds. At a six-second gap that left PowerShell running 41% of the time,
# for ever — the gauge was costing more of the machine than it was reporting on.
# Thirty seconds puts the duty cycle near one part in eight, and the watcher
# only asks at all while somebody is looking at the panel.
GPU_INTERVAL = 30.0
GPU_TIMEOUT = 8


class _FILETIME(ctypes.Structure):
    _fields_ = [("low", wintypes.DWORD), ("high", wintypes.DWORD)]


class _MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [("dwLength", wintypes.DWORD), ("dwMemoryLoad", wintypes.DWORD),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]


def _system_times():
    idle, kernel, user = _FILETIME(), _FILETIME(), _FILETIME()
    ctypes.windll.kernel32.GetSystemTimes(
        ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user))
    whole = lambda f: (f.high << 32) | f.low
    return whole(idle), whole(kernel), whole(user)


_last_times = None


def cpu_percent() -> float:
    """Busy time since the previous call. The first call has no previous, so it
    reports nothing rather than guessing."""
    global _last_times
    try:
        idle, kernel, user = _system_times()
    except Exception:
        return 0.0
    previous, _last_times = _last_times, (idle, kernel, user)
    if previous is None:
        return 0.0
    idle_delta = idle - previous[0]
    busy_delta = (kernel - previous[1]) + (user - previous[2])
    if busy_delta <= 0:
        return 0.0
    return round(max(0.0, min(100.0, 100.0 * (1 - idle_delta / busy_delta))), 1)


def memory() -> dict:
    status = _MEMORYSTATUSEX()
    status.dwLength = ctypes.sizeof(_MEMORYSTATUSEX)
    try:
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status))
    except Exception:
        return {"percent": 0.0, "used": 0.0, "total": 0.0}
    gib = 1024 ** 3
    total = status.ullTotalPhys / gib
    return {"percent": float(status.dwMemoryLoad),
            "used": round(total - status.ullAvailPhys / gib, 1),
            "total": round(total, 1)}


def storage(drive: str = "C:\\") -> dict:
    try:
        usage = shutil.disk_usage(drive)
    except OSError:
        return {"percent": 0.0, "used": 0.0, "total": 0.0}
    gib = 1024 ** 3
    return {"percent": round(100.0 * usage.used / usage.total, 1),
            "used": round(usage.used / gib),
            "total": round(usage.total / gib)}


_gpu = {"percent": 0.0, "at": 0.0}
_gpu_lock = threading.Lock()

# Every vendor answers this, where nvidia-smi only speaks for one card.
_GPU_QUERY = (
    "(Get-Counter '\\GPU Engine(*)\\Utilization Percentage' "
    "-ErrorAction SilentlyContinue).CounterSamples "
    "| Measure-Object -Property CookedValue -Sum "
    "| ForEach-Object { [math]::Round($_.Sum, 1) }")


def gpu_percent(force: bool = False) -> float:
    """Summed engine utilisation, from the performance counters. Cached: the
    read costs the better part of a second, which is far too dear to repeat."""
    now = time.monotonic()
    with _gpu_lock:
        fresh = (now - _gpu["at"]) < GPU_INTERVAL
    if fresh and not force:
        return _gpu["percent"]
    value = 0.0
    try:
        done = subprocess.run(["powershell", "-NoProfile", "-Command", _GPU_QUERY],
                              capture_output=True, text=True, timeout=GPU_TIMEOUT)
        value = min(100.0, max(0.0, float(done.stdout.strip() or 0)))
    except Exception:
        value = 0.0
    with _gpu_lock:
        _gpu.update(percent=round(value, 1), at=now)
    return _gpu["percent"]


def snapshot() -> dict:
    """One reading of every instrument, ready to be shown and forgotten.

    Never blocks: the GPU figure is whatever the watcher last cached. A gauge
    that stalls the panel to update itself is worse than a gauge a few seconds
    behind.
    """
    return {"cpu": cpu_percent(), "gpu": _gpu["percent"],
            "ram": memory(), "disk": storage()}


def watch_gpu(stop: threading.Event, wanted=None) -> None:
    """Refresh the expensive figure on its own thread, out of everyone's way —
    and only while `wanted()` says someone is actually looking at it. An
    unwatched gauge has no business spawning a process every few seconds."""
    while not stop.is_set():
        if wanted is None or wanted():
            gpu_percent(force=True)
        stop.wait(GPU_INTERVAL)
