"""House configuration: the folders, apps, and settings Alfred may touch.

Everything here is an allowlist. Absence means refusal — adapters never
consult this module; by the time an adapter runs, the validator has already
enforced it.
"""

from pathlib import Path

# Folders open_file may serve from (paths are resolved before checking).
ALLOWED_FOLDERS: list[Path] = [
    Path.home() / "Documents",
    Path.home() / "Downloads",
    Path.home() / "Desktop",
]

# launch_app menu: friendly name -> executable. Bare names only — resolved
# via the system PATH, never through a shell.
ALLOWED_APPS: dict[str, str] = {
    "notepad": "notepad.exe",
    "calculator": "calc.exe",
    "explorer": "explorer.exe",
}

# settings_change menu: key -> the exact values permitted.
SETTINGS_POLICY: dict[str, frozenset[str]] = {
    "app_theme": frozenset({"light", "dark"}),
}

MAX_PLAN_STEPS = 10
MAX_PLAN_BYTES = 20_000
MAX_CLIPBOARD_CHARS = 10_000

DATA_DIR = Path.home() / ".alfred"
