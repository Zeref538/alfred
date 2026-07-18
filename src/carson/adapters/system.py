"""Settings adapters: whitelisted registry keys only, snapshot before change."""

import ctypes
import winreg

from .. import schemas
from ..undo import RevertHandle

_PERSONALIZE = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
_APPS_LIGHT = "AppsUseLightTheme"


def _read_theme() -> int:
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _PERSONALIZE) as key:
        return winreg.QueryValueEx(key, _APPS_LIGHT)[0]


def _write_theme(value: int) -> None:
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _PERSONALIZE, 0,
                        winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, _APPS_LIGHT, 0, winreg.REG_DWORD, value)
    # nudge running apps to notice the theme change
    ctypes.windll.user32.SendNotifyMessageW(0xFFFF, 0x001A, 0, "ImmersiveColorSet")


def settings_change(args: schemas.SettingsChange) -> RevertHandle:
    # validator guaranteed key/value membership; only app_theme exists in v1
    previous = _read_theme()
    _write_theme(1 if args.value == "light" else 0)
    return RevertHandle(
        "settings_change",
        f"restore app_theme to {'light' if previous else 'dark'}",
        lambda: _write_theme(previous),
    )


def toggle_do_not_disturb(args: schemas.ToggleDnd) -> None:
    # At-risk adapter (Focus Assist has no stable public API). Honest refusal
    # beats a flaky toggle; see the adapter risk table in PLAN.md.
    raise RuntimeError("do-not-disturb is not yet reliable on this build; parked as at-risk")
