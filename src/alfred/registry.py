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
    # The consent ladder — the higher the rung, the heavier the consent.
    # A plan is gated once, at the highest tier any of its steps carries.
    AT_LIBERTY = 0    # read-only / instantly reversible: runs at once, silently
    ANNOUNCED = 1     # reversible state change: runs at once, flashed, undoable — no yes
    CONFIRM = 2       # consequential: one plain yes (click "engage", say "yes")
    UNDER_SEAL = 3    # reaches the filesystem: type exactly "yes i approve please proceed"


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
    ActionSpec("focus_tab", Tier.AT_LIBERTY, False, schemas.FocusTab,
               "Switch to a browser tab that is already open"),
    ActionSpec("launch_app", Tier.ANNOUNCED, False, schemas.LaunchApp,
               "Start an allowlisted application"),
    ActionSpec("media_control", Tier.ANNOUNCED, False, schemas.MediaControl,
               "Play, pause, or skip media"),
    ActionSpec("set_volume", Tier.ANNOUNCED, True, schemas.SetVolume,
               "Set the master volume (0-100)"),
    ActionSpec("toggle_do_not_disturb", Tier.ANNOUNCED, True, schemas.ToggleDnd,
               "Mute or restore notifications"),
    ActionSpec("open_file", Tier.UNDER_SEAL, False, schemas.OpenFile,
               "Open a file from a whitelisted folder"),
    ActionSpec("clipboard_read", Tier.AT_LIBERTY, False, schemas.NoArgs,
               "Read the clipboard (never fed to the planner)"),
    ActionSpec("clipboard_write", Tier.ANNOUNCED, True, schemas.ClipboardWrite,
               "Write text to the clipboard (previous contents snapshotted)"),
    ActionSpec("window_layout", Tier.ANNOUNCED, True, schemas.WindowLayout,
               "Arrange the focused window"),
    ActionSpec("settings_change", Tier.CONFIRM, True, schemas.SettingsChange,
               "Change an allowlisted setting"),
]

REGISTRY: dict[str, ActionSpec] = {spec.name: spec for spec in _SPECS}
