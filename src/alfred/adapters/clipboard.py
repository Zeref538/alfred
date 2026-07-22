"""Clipboard via fixed PowerShell argv — data travels over stdin/stdout,
never through string interpolation, so content can't become command."""

import subprocess

from .. import schemas
from ..undo import RevertHandle

_GET = ["powershell", "-NoProfile", "-Command", "Get-Clipboard -Raw"]
_SET = ["powershell", "-NoProfile", "-Command", "$input | Set-Clipboard"]


def _get() -> str:
    out = subprocess.run(_GET, capture_output=True, timeout=10,
                         creationflags=subprocess.CREATE_NO_WINDOW)
    return out.stdout.decode("utf-8", errors="replace").rstrip("\r\n")


def _set(text: str) -> None:
    subprocess.run(_SET, input=text.encode("utf-8"), capture_output=True, timeout=10,
                   creationflags=subprocess.CREATE_NO_WINDOW)


def read(args: schemas.NoArgs) -> None:
    # Read for the *user* (palette prints it). Never fed to a planner.
    print(_get())


def write(args: schemas.ClipboardWrite) -> RevertHandle:
    previous = _get()
    _set(args.text)
    return RevertHandle(
        "clipboard_write",
        "restore the previous clipboard contents",
        lambda: _set(previous),
    )
