"""Typed argument models — "the measure of every request".

The registry constrains action *names*; these models constrain the
*arguments*, where the real danger lives. Every model forbids unknown fields,
and fields carry per-action policy: URL schemes, path containment, allowlist
membership, value ranges. A plan that fails here never reaches an adapter.
"""

from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from . import config


class Args(BaseModel):
    model_config = ConfigDict(extra="forbid")


class NoArgs(Args):
    pass


class OpenUrl(Args):
    url: str = Field(min_length=1, max_length=2048)

    @field_validator("url")
    @classmethod
    def http_only(cls, v: str) -> str:
        parts = urlsplit(v)
        if parts.scheme not in ("http", "https") or not parts.netloc:
            raise ValueError("only http(s) URLs with a host are served")
        return v


class WebSearch(Args):
    query: str = Field(min_length=1, max_length=256)

    @field_validator("query")
    @classmethod
    def printable(cls, v: str) -> str:
        if any(ch in v for ch in "\r\n\x00"):
            raise ValueError("query must be a single line of text")
        return v.strip()


class FocusApp(Args):
    title: str = Field(min_length=1, max_length=64)


class PlayMedia(Args):
    """A media page to open and set playing. http(s) only, as ever."""
    url: str = Field(min_length=1, max_length=2048)

    @field_validator("url")
    @classmethod
    def http_only(cls, v: str) -> str:
        parts = urlsplit(v)
        if parts.scheme not in ("http", "https") or not parts.netloc:
            raise ValueError("only http(s) URLs with a host are served")
        return v


class FocusTab(Args):
    """The spoken name of a tab. Never a URL: Alfred switches to a tab that is
    already open, he does not navigate one anywhere."""
    name: str = Field(min_length=1, max_length=80)


class LaunchApp(Args):
    app: str

    @field_validator("app")
    @classmethod
    def on_the_menu(cls, v: str) -> str:
        if v not in config.ALLOWED_APPS:
            raise ValueError(f"'{v}' is not a registered application")
        return v


class MediaControl(Args):
    command: Literal["play_pause", "next", "previous", "stop"]


class SetVolume(Args):
    level: int = Field(ge=0, le=100)


class ToggleDnd(Args):
    enabled: bool


class OpenFile(Args):
    path: str = Field(min_length=1, max_length=1024)

    @field_validator("path")
    @classmethod
    def contained(cls, v: str) -> str:
        resolved = Path(v).expanduser().resolve()
        if not any(resolved.is_relative_to(f) for f in config.ALLOWED_FOLDERS):
            raise ValueError("path is outside the whitelisted folders")
        return str(resolved)


class ClipboardWrite(Args):
    text: str = Field(max_length=config.MAX_CLIPBOARD_CHARS)


class WindowLayout(Args):
    preset: Literal["left_half", "right_half", "maximized", "minimized"]


class SettingsChange(Args):
    key: str
    value: str

    @model_validator(mode="after")
    def on_the_menu(self) -> "SettingsChange":
        allowed = config.SETTINGS_POLICY.get(self.key)
        if allowed is None:
            raise ValueError(f"setting '{self.key}' is not on the menu")
        if self.value not in allowed:
            raise ValueError(
                f"setting '{self.key}' accepts {sorted(allowed)}, not '{self.value}'"
            )
        return self
