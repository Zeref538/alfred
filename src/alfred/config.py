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

# launch_app menu: friendly name -> executable or Start Menu shortcut.
# Never launched through a shell. `alfred apps scan` writes the user's own
# registry to ~/.alfred/apps.yaml, which replaces these built-ins.
_BUILTIN_APPS: dict[str, str] = {
    "notepad": "notepad.exe",
    "calculator": "calc.exe",
    "explorer": "explorer.exe",
}

APPS_FILE = Path.home() / ".alfred" / "apps.yaml"


def load_registered_apps(path: Path = APPS_FILE) -> dict[str, str]:
    if not path.exists():
        return dict(_BUILTIN_APPS)
    import yaml
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        apps = {str(k).lower(): str(v) for k, v in loaded.items()}
        return {**_BUILTIN_APPS, **apps}
    except Exception:
        return dict(_BUILTIN_APPS)


ALLOWED_APPS: dict[str, str] = load_registered_apps()

# settings_change menu: key -> the exact values permitted.
SETTINGS_POLICY: dict[str, frozenset[str]] = {
    "app_theme": frozenset({"light", "dark"}),
}

MAX_PLAN_STEPS = 10
MAX_PLAN_BYTES = 20_000
MAX_CLIPBOARD_CHARS = 10_000

DATA_DIR = Path.home() / ".alfred"
