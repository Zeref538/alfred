"""Persistent preferences: ~/.alfred/settings.yaml.

Precedence for every knob: environment variable (ALFRED_<KEY>) beats the
settings file beats the built-in default — so a shell override always wins,
and the settings page edits the file underneath.
"""

import os

import yaml

from . import config

SETTINGS_FILE = config.DATA_DIR / "settings.yaml"

DEFAULTS: dict[str, str] = {
    "voice_pace": "1.18",     # higher = brisker speech
    "voice_volume": "0.85",   # Alfred's own loudness, 0-1, independent of master
    "whisper": "small",       # STT model: tiny | base | small
    "piper_voice": "en_GB-alan-medium",
    "model": "qwen3.5:2b",    # planner model (Ollama tag)
    "search": "https://www.google.com/search?q=",
}


def load() -> dict[str, str]:
    if not SETTINGS_FILE.exists():
        return {}
    try:
        doc = yaml.safe_load(SETTINGS_FILE.read_text(encoding="utf-8")) or {}
        return {str(k): str(v) for k, v in doc.items()}
    except Exception:
        return {}


def save(values: dict[str, str]) -> None:
    known = {k: str(v) for k, v in values.items() if k in DEFAULTS}
    merged = {**load(), **known}
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(yaml.safe_dump(merged, sort_keys=True),
                             encoding="utf-8")


def get(key: str, default: str | None = None) -> str:
    env = os.environ.get("ALFRED_" + key.upper())
    if env is not None:
        return env
    return load().get(key, default if default is not None else DEFAULTS[key])


def current() -> dict[str, str]:
    return {key: get(key) for key in DEFAULTS}
