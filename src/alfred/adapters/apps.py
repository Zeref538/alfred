import ctypes
import ctypes.wintypes as wt
import os
import subprocess
from pathlib import Path

from .. import config, schemas

user32 = ctypes.windll.user32


def launch_app(args: schemas.LaunchApp) -> None:
    # validator guaranteed membership; no shell involved
    target = config.ALLOWED_APPS[args.app]
    if target.lower().endswith(".lnk"):
        import os
        os.startfile(target)  # Start Menu shortcut — the OS resolves it
    else:
        subprocess.Popen([target], shell=False)


START_MENU_DIRS = [
    Path(os.environ.get("APPDATA", "")) / "Microsoft/Windows/Start Menu/Programs",
    Path(os.environ.get("PROGRAMDATA", "")) / "Microsoft/Windows/Start Menu/Programs",
]


def scan_start_menu(roots: list[Path] | None = None) -> dict[str, str]:
    """Every Start Menu shortcut becomes a registrable app: name -> .lnk path.
    Uninstallers and obvious noise are left out."""
    apps: dict[str, str] = {}
    skip = ("uninstall", "readme", "website", "help")
    for root in roots or START_MENU_DIRS:
        if not root.is_dir():
            continue
        for lnk in sorted(root.rglob("*.lnk")):
            name = lnk.stem.strip().lower()
            if name and not any(word in name for word in skip):
                apps.setdefault(name, str(lnk))
    return apps


def focus_app(args: schemas.FocusApp) -> None:
    target = args.title.lower()
    windows: list[tuple[int, str]] = []

    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def visit(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            length = user32.GetWindowTextLengthW(hwnd)
            if length:
                buf = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buf, length + 1)
                windows.append((hwnd, buf.value))
        return True

    user32.EnumWindows(visit, 0)
    # the whole phrase first; failing that any solid word of it, so "google
    # chrome" still finds a window merely titled "... - Chrome"
    hwnd = next((h for h, title in windows if target in title.lower()), None)
    if hwnd is None:
        words = [w for w in target.split() if len(w) >= 4]
        hwnd = next((h for h, title in windows
                     if any(w in title.lower() for w in words)), None)
    if hwnd is None:
        open_now = ", ".join(dict.fromkeys(
            t.split(" - ")[-1] for _, t in windows if t.strip()))[:180]
        raise RuntimeError(
            f"nothing called '{args.title}' is open, sir"
            + (f" — I can see: {open_now}" if open_now else ""))
    user32.ShowWindow(hwnd, 9)  # SW_RESTORE, in case minimized
    user32.SetForegroundWindow(hwnd)
