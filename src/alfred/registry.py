"""The service menu: the only actions Alfred can ever perform.

New capabilities are new registry entries — nothing else. Each entry declares
its consent tier, whether it is reversible, and the typed argument model the
validator enforces.
"""

from dataclasses import dataclass
from enum import IntEnum

from pydantic import BaseModel

from . import schemas

REGISTRY_VERSION = 1


class Tier(IntEnum):
    AT_LIBERTY = 0  # read-only / instantly reversible: executes immediately
    ANNOUNCED = 1  # state changes: announced with a cancelable notice
    BY_YOUR_LEAVE = 2  # settings / files: explicit confirmation required


@dataclass(frozen=True)
class ActionSpec:
    name: str
    tier: Tier
    reversible: bool
    args: type[BaseModel]
    summary: str


_SPECS = [
    ActionSpec("open_url", Tier.AT_LIBERTY, False, schemas.OpenUrl,
               "Open a web page in the browser"),
    ActionSpec("web_search", Tier.AT_LIBERTY, False, schemas.WebSearch,
               "Run a web search in the browser"),
    ActionSpec("focus_app", Tier.AT_LIBERTY, False, schemas.FocusApp,
               "Bring a window to the front by title"),
    ActionSpec("launch_app", Tier.ANNOUNCED, False, schemas.LaunchApp,
               "Start an allowlisted application"),
    ActionSpec("media_control", Tier.ANNOUNCED, False, schemas.MediaControl,
               "Play, pause, or skip media"),
    ActionSpec("set_volume", Tier.ANNOUNCED, True, schemas.SetVolume,
               "Set the master volume (0-100)"),
    ActionSpec("toggle_do_not_disturb", Tier.ANNOUNCED, True, schemas.ToggleDnd,
               "Mute or restore notifications"),
    ActionSpec("open_file", Tier.BY_YOUR_LEAVE, False, schemas.OpenFile,
               "Open a file from a whitelisted folder"),
    ActionSpec("clipboard_read", Tier.AT_LIBERTY, False, schemas.NoArgs,
               "Read the clipboard (never fed to the planner)"),
    ActionSpec("clipboard_write", Tier.ANNOUNCED, True, schemas.ClipboardWrite,
               "Write text to the clipboard (previous contents snapshotted)"),
    ActionSpec("window_layout", Tier.ANNOUNCED, True, schemas.WindowLayout,
               "Arrange the focused window"),
    ActionSpec("settings_change", Tier.BY_YOUR_LEAVE, True, schemas.SettingsChange,
               "Change an allowlisted setting"),
]

REGISTRY: dict[str, ActionSpec] = {spec.name: spec for spec in _SPECS}
