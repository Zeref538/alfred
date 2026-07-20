"""The bell pull: a global hotkey that summons the palette.

The configured combination (settings key `summon_hotkey`, default Ctrl+Alt+C)
anywhere opens a fresh console running the REPL. Implemented with RegisterHotKey
via ctypes — no keyboard hooking, no extra dependencies, and the OS refuses us
cleanly if the combination is already taken.
"""

import ctypes
import ctypes.wintypes as wt
import subprocess
import sys

user32 = ctypes.windll.user32

_MOD_ALT = 0x0001
_MOD_CONTROL = 0x0002
_MOD_SHIFT = 0x0004
_MOD_WIN = 0x0008
_MOD_NOREPEAT = 0x4000
_WM_HOTKEY = 0x0312
_HOTKEY_ID = 1

_MODIFIERS = {"ctrl": _MOD_CONTROL, "control": _MOD_CONTROL, "alt": _MOD_ALT,
              "shift": _MOD_SHIFT, "win": _MOD_WIN, "cmd": _MOD_WIN}


def parse_hotkey(combo: str) -> tuple[int, int]:
    """'ctrl+alt+c' -> (mods, virtual-key). The last token is the key; raises
    ValueError on an empty or unparseable combination."""
    tokens = [t.strip().lower() for t in combo.split("+") if t.strip()]
    if not tokens:
        raise ValueError("empty hotkey")
    *mod_names, key = tokens
    mods = _MOD_NOREPEAT
    for name in mod_names:
        if name not in _MODIFIERS:
            raise ValueError(f"unknown modifier '{name}'")
        mods |= _MODIFIERS[name]
    if len(key) != 1 or not key.isalnum():
        raise ValueError(f"'{key}' is not a single letter or digit")
    return mods, ord(key.upper())


def open_palette() -> None:
    import os
    ui = os.environ.get("ALFRED_UI", "web")
    subprocess.Popen([sys.executable, "-m", "alfred", ui],
                     creationflags=subprocess.CREATE_NO_WINDOW)


def register() -> None:
    """Claim the configured hotkey or raise; callers must unregister()."""
    from . import settings
    combo = settings.get("summon_hotkey")
    mods, vk = parse_hotkey(combo)
    if not user32.RegisterHotKey(None, _HOTKEY_ID, mods, vk):
        raise RuntimeError(f"{combo} is already spoken for; Alfred cannot answer the bell")


def unregister() -> None:
    user32.UnregisterHotKey(None, _HOTKEY_ID)


def summon_loop(check_only: bool = False) -> None:
    from . import settings
    combo = settings.get("summon_hotkey").upper()
    register()
    try:
        if check_only:
            print(f"The bell is answered: {combo} registered and released.")
            return
        print(f"At your bell, sir — {combo} to summon. Close this window to dismiss me.")
        msg = wt.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            if msg.message == _WM_HOTKEY and msg.wParam == _HOTKEY_ID:
                open_palette()
    finally:
        unregister()
