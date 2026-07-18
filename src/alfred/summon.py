"""The bell pull: a global hotkey that summons the palette.

Ctrl+Alt+C anywhere opens a fresh console running the REPL. Implemented with
RegisterHotKey via ctypes — no keyboard hooking, no extra dependencies, and
the OS refuses us cleanly if the combination is already taken.
"""

import ctypes
import ctypes.wintypes as wt
import subprocess
import sys

user32 = ctypes.windll.user32

_MOD_ALT = 0x0001
_MOD_CONTROL = 0x0002
_MOD_NOREPEAT = 0x4000
_VK_C = 0x43
_WM_HOTKEY = 0x0312
_HOTKEY_ID = 1


def open_palette() -> None:
    subprocess.Popen([sys.executable, "-m", "alfred", "hud"],
                     creationflags=subprocess.CREATE_NO_WINDOW)


def register() -> None:
    """Claim Ctrl+Alt+C or raise; callers must unregister()."""
    if not user32.RegisterHotKey(None, _HOTKEY_ID,
                                 _MOD_CONTROL | _MOD_ALT | _MOD_NOREPEAT, _VK_C):
        raise RuntimeError("Ctrl+Alt+C is already spoken for; Alfred cannot answer the bell")


def unregister() -> None:
    user32.UnregisterHotKey(None, _HOTKEY_ID)


def summon_loop(check_only: bool = False) -> None:
    register()
    try:
        if check_only:
            print("The bell is answered: Ctrl+Alt+C registered and released.")
            return
        print("At your bell, sir — Ctrl+Alt+C to summon. Close this window to dismiss me.")
        msg = wt.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            if msg.message == _WM_HOTKEY and msg.wParam == _HOTKEY_ID:
                open_palette()
    finally:
        unregister()
