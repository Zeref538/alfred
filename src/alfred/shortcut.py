"""A door on the desktop.

Alfred should not need a terminal to be summoned. This draws his crest as a
Windows icon and puts a shortcut on the Desktop (and in the Start Menu) that
launches him windowless — double-click, and the HUD opens.

    alfred install     put the shortcut there
    alfred uninstall   take it away again

Nothing is installed system-wide and no registry key is written: a shortcut is
a file, and removing it removes everything this did.
"""

import subprocess
import sys
from pathlib import Path

from . import config

ICON_FILE = config.DATA_DIR / "alfred.ico"
SHORTCUT_NAME = "Alfred.lnk"
ICON_SIZES = (16, 24, 32, 48, 64, 128, 256)

_INK = (4, 8, 15, 255)
_CYAN = (57, 215, 255, 255)
_WHITE = (234, 255, 255, 255)


def _draw_crest(size: int):
    """The bowtie inside a hex ring, drawn large and scaled down so the edges
    stay clean at 16px."""
    from PIL import Image, ImageDraw
    scale = 8
    big = size * scale
    image = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    unit = big / 64.0

    def at(x, y):
        return (x * unit, y * unit)

    draw.ellipse([at(2, 2), at(62, 62)], fill=_INK)
    hexagon = [at(32, 3), at(58, 17), at(58, 47), at(32, 61), at(6, 47), at(6, 17)]
    draw.polygon(hexagon, outline=_CYAN, width=max(1, int(2.5 * unit)))
    draw.polygon([at(32, 32), at(18, 23), at(18, 41)], fill=_CYAN)
    draw.polygon([at(32, 32), at(46, 23), at(46, 41)], fill=_CYAN)
    draw.ellipse([at(28, 28), at(36, 36)], fill=_WHITE)
    return image.resize((size, size), Image.LANCZOS)


def make_icon(path: Path = None) -> Path:
    path = path or ICON_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    frames = [_draw_crest(s) for s in ICON_SIZES]
    frames[-1].save(path, format="ICO",
                    sizes=[(s, s) for s in ICON_SIZES])
    return path


def _windowless_python() -> str:
    """pythonw.exe runs with no console — a double-click shouldn't flash a
    black box at anyone."""
    exe = Path(sys.executable)
    windowless = exe.with_name("pythonw.exe")
    return str(windowless if windowless.exists() else exe)


def _make_link(target: Path, icon: Path, python: str) -> None:
    """Written through WScript.Shell, so no extra dependency is needed."""
    script = (
        "$s = (New-Object -ComObject WScript.Shell).CreateShortcut('%s');"
        "$s.TargetPath = '%s';"
        "$s.Arguments = '-m alfred web';"
        "$s.WorkingDirectory = '%s';"
        "$s.IconLocation = '%s';"
        "$s.Description = 'Alfred — your butler';"
        "$s.Save()"
    ) % (target, python, Path.home(), icon)
    subprocess.run(["powershell", "-NoProfile", "-Command", script],
                   capture_output=True, timeout=30)


def desktop() -> Path:
    return Path.home() / "Desktop"


def start_menu() -> Path:
    import os
    return (Path(os.environ.get("APPDATA", Path.home()))
            / "Microsoft" / "Windows" / "Start Menu" / "Programs")


def install() -> list[Path]:
    icon = make_icon()
    python = _windowless_python()
    made = []
    for folder in (desktop(), start_menu()):
        if not folder.is_dir():
            continue
        link = folder / SHORTCUT_NAME
        _make_link(link, icon, python)
        if link.exists():
            made.append(link)
    return made


def uninstall() -> list[Path]:
    removed = []
    for folder in (desktop(), start_menu()):
        link = folder / SHORTCUT_NAME
        if link.exists():
            link.unlink()
            removed.append(link)
    ICON_FILE.unlink(missing_ok=True)
    return removed
