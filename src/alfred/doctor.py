"""`alfred doctor` — a quick self-check, not a monitor. Reuses telemetry's
instruments and the same lockfile web.py already keeps; adds nothing new to
watch, just reads what is already there."""

import importlib.util
import time

from . import config, telemetry
from .web import _lockfile, _running_instance

_OPTIONAL_EXTRAS = {
    "voice": ["faster_whisper", "sounddevice"],
    "ui (tray)": ["pystray", "PIL"],
    "motion": ["cv2"],
    "vision": ["mediapipe"],
    "hotkey": ["keyboard"],
}


def _extra_installed(modules: list[str]) -> bool:
    return all(importlib.util.find_spec(m) is not None for m in modules)


def checks() -> list[tuple[bool, str]]:
    results = []

    running = _running_instance()
    lock = _lockfile()
    if lock.exists() and not running:
        results.append((False, "stale lockfile at %s (a crashed session) — "
                                "`alfred stop` or delete it" % lock))
    else:
        results.append((True, f"running instance: {running or 'none'}"))

    # cpu_percent() needs two samples to report anything real (the first call
    # has no previous reading to diff against) — prime it with a throwaway
    # call rather than report a false 0%.
    telemetry.cpu_percent()
    time.sleep(0.15)
    cpu = telemetry.cpu_percent()
    results.append((cpu < 90, f"cpu: {cpu:.0f}% busy"))

    gpu = telemetry.gpu_percent(force=True)
    results.append((gpu < 90, f"gpu: {gpu:.0f}% busy"))

    disk = telemetry.storage()
    ok = disk["percent"] < 90
    results.append((ok, f"disk: {disk['used']}/{disk['total']} GiB used "
                         f"({disk['percent']}%)"))

    ram = telemetry.memory()
    results.append((ram["percent"] < 90,
                    f"memory: {ram['used']}/{ram['total']} GiB used "
                    f"({ram['percent']}%)"))

    for folder in config.ALLOWED_FOLDERS:
        results.append((folder.is_dir(), f"allowed folder exists: {folder}"))

    return results


def optional_extras() -> list[tuple[bool, str]]:
    return [(_extra_installed(mods), label) for label, mods in _OPTIONAL_EXTRAS.items()]


def main() -> int:
    all_ok = True
    for ok, line in checks():
        mark = "OK  " if ok else "!!  "
        print(f"{mark}{line}")
        all_ok = all_ok and ok
    extras = ", ".join(label for present, label in optional_extras() if present)
    print(f"Extras installed: {extras or 'none'}")
    print("All well, sir." if all_ok else "A few things want attention, sir.")
    return 0 if all_ok else 1
