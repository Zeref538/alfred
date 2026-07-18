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
    found: list[int] = []

    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def visit(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            length = user32.GetWindowTextLengthW(hwnd)
            if length:
                buf = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buf, length + 1)
                if target in buf.value.lower():
                    found.append(hwnd)
                    return False
        return True

    user32.EnumWindows(visit, 0)
    if not found:
        raise RuntimeError(f"no visible window matching '{args.title}'")
    user32.ShowWindow(found[0], 9)  # SW_RESTORE, in case minimized
    user32.SetForegroundWindow(found[0])
