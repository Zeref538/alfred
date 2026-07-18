"""Arrange the foreground window. Reversible: the previous rect is snapshotted."""

import ctypes
import ctypes.wintypes as wt

from .. import schemas
from ..undo import RevertHandle

user32 = ctypes.windll.user32

_SW_MAXIMIZE = 3
_SW_MINIMIZE = 6
_SW_RESTORE = 9


def _halves() -> dict[str, tuple[int, int, int, int]]:
    w = user32.GetSystemMetrics(0)
    h = user32.GetSystemMetrics(1)
    return {
        "left_half": (0, 0, w // 2, h),
        "right_half": (w // 2, 0, w - w // 2, h),
    }


def window_layout(args: schemas.WindowLayout) -> RevertHandle:
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        raise RuntimeError("no foreground window to arrange")

    rect = wt.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    before = (rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top)

    if args.preset == "maximized":
        user32.ShowWindow(hwnd, _SW_MAXIMIZE)
    elif args.preset == "minimized":
        user32.ShowWindow(hwnd, _SW_MINIMIZE)
    else:
        x, y, w, h = _halves()[args.preset]
        user32.ShowWindow(hwnd, _SW_RESTORE)
        user32.MoveWindow(hwnd, x, y, w, h, True)

    def put_back() -> None:
        user32.ShowWindow(hwnd, _SW_RESTORE)
        user32.MoveWindow(hwnd, *before, True)

    return RevertHandle("window_layout", "restore the window's previous place", put_back)
