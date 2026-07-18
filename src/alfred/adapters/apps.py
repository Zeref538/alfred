import ctypes
import ctypes.wintypes as wt
import subprocess

from .. import config, schemas

user32 = ctypes.windll.user32


def launch_app(args: schemas.LaunchApp) -> None:
    # validator guaranteed membership; no shell involved
    subprocess.Popen([config.ALLOWED_APPS[args.app]], shell=False)


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
