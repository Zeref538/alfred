"""Deterministic adapters: the only hands Alfred has.

Each adapter is a plain function taking the validated, typed args for its
action. Adapters trust their input — by the time they run, the validator and
gate have already ruled. State-changing adapters return a RevertHandle.
"""

from ..executor import Adapter
from . import apps, browser, clipboard, files, media, system, windows


def build_adapters() -> dict[str, Adapter]:
    return {
        "open_url": browser.open_url,
        "web_search": browser.web_search,
        "focus_app": apps.focus_app,
        "launch_app": apps.launch_app,
        "media_control": media.media_control,
        "set_volume": media.set_volume,
        "toggle_do_not_disturb": system.toggle_do_not_disturb,
        "open_file": files.open_file,
        "clipboard_read": clipboard.read,
        "clipboard_write": clipboard.write,
        "window_layout": windows.window_layout,
        "settings_change": system.settings_change,
    }
